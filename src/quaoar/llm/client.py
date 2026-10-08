# cohere through pydantic-ai: one model per scan, keys rotate on rate limits, answers cached
import os
from collections.abc import Callable, Sequence

from pydantic import BaseModel, SecretStr
from pydantic_ai import Agent, ToolOutput
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models import Model

from quaoar.clock import ClockPort
from quaoar.domain.ids import canonical_json, sha256_hex
from quaoar.events import Emitter
from quaoar.llm.prompts import PROMPT_VERSION, instructions, wrap_data
from quaoar.serp.keys import fingerprint
from quaoar.serp.ledger import Ledger, LlmCall
from quaoar.serp.replay import ReplayStore

# the pydantic-ai banner would land in our CLI output
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MAX_CONTEXT_BYTES = 24 * 1024
ROTATE_ON = frozenset({429})

ModelFactory = Callable[[str, str], Model]


class LlmError(RuntimeError):
    pass


class ContextTooLargeError(LlmError):
    pass


def cohere_model(model_name: str, api_key: str) -> Model:
    from pydantic_ai.models.cohere import CohereModel
    from pydantic_ai.providers.cohere import CohereProvider

    return CohereModel(model_name, provider=CohereProvider(api_key=api_key))


class LlmClient:
    def __init__(
        self,
        *,
        ledger: Ledger,
        clock: ClockPort,
        model_name: str,
        keys: Sequence[SecretStr],
        factory: ModelFactory = cohere_model,
        replay: ReplayStore | None = None,
        emit: Emitter | None = None,
    ) -> None:
        self._ledger, self._clock, self._model = ledger, clock, model_name
        self._keys = list(keys)
        self._spent: set[str] = set()
        self._factory, self._replay, self._emit = factory, replay, emit

    def extract[T: BaseModel](
        self, task: str, output: type[T], text: str, parent: str | None = None
    ) -> T:
        data = wrap_data(text)
        if len(data.encode()) > MAX_CONTEXT_BYTES:
            raise ContextTooLargeError(f"{task}: {len(data.encode())} bytes over the context cap")
        request_hash = self.request_hash(task, output, text)
        start = self._clock.ns()

        # replay and the ledger answer for free; the model is only asked once per text
        body = self._replay.get(request_hash) if self._replay is not None else None
        body = body or self._ledger.llm_body(request_hash)
        if body is not None:
            self._report(
                task, request_hash, None, 0, 0, self._clock.ns() - start, parent, cached=True
            )
            return output.model_validate_json(body)
        return self._live(task, output, data, request_hash, start, parent)

    def request_hash(self, task: str, output: type[BaseModel], text: str) -> str:
        return sha256_hex(
            canonical_json(
                {
                    "model": self._model,
                    "task": task,
                    "prompt": PROMPT_VERSION,
                    "schema": output.__name__,
                    "text": sha256_hex(text),
                }
            )
        )

    def _live[T: BaseModel](
        self,
        task: str,
        output: type[T],
        data: str,
        request_hash: str,
        start: int,
        parent: str | None,
    ) -> T:
        for key in self._keys:
            fp = fingerprint(key.get_secret_value())
            if fp in self._spent:
                continue
            agent = Agent(
                self._factory(self._model, key.get_secret_value()),
                output_type=ToolOutput(output),
                instructions=instructions(task),
                retries=1,
            )
            try:
                result = agent.run_sync(data)
            except ModelHTTPError as exc:
                if exc.status_code in ROTATE_ON:
                    self._spent.add(fp)
                    continue
                raise LlmError(f"{task}: model error {exc.status_code}") from None
            except UnexpectedModelBehavior as exc:
                raise LlmError(f"{task}: output failed validation") from exc

            latency = self._clock.ns() - start
            usage = result.usage
            body = result.output.model_dump_json().encode()
            self._ledger.record_llm(
                LlmCall(
                    request_hash=request_hash,
                    model=self._model,
                    task=task,
                    body_sha256=self._ledger.blobs.put(body),
                    key_fp=fp,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    latency_ns=latency,
                    created_at=self._clock.now(),
                )
            )
            self._report(
                task,
                request_hash,
                fp,
                usage.input_tokens,
                usage.output_tokens,
                latency,
                parent,
                cached=False,
            )
            return result.output
        raise LlmError(f"{task}: every Cohere key is rate limited")

    def _report(
        self,
        task: str,
        request_hash: str,
        key_fp: str | None,
        tokens_in: int,
        tokens_out: int,
        latency_ns: int,
        parent: str | None,
        *,
        cached: bool,
    ) -> None:
        if self._emit is None:
            return
        self._emit(
            "llm",
            {
                "task": task,
                "model": self._model,
                "request": request_hash[:16],
                "cached": cached,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": round(latency_ns / 1e6, 3),
                "key": key_fp,
            },
            parent=parent,
        )
