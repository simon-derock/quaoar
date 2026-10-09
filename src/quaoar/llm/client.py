# cohere through pydantic-ai: one model per scan, keys rotate on rate limits, answers cached
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

import httpx
from pydantic import BaseModel, SecretStr
from pydantic_ai import Agent, AgentRunResult, Tool, ToolOutput
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

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
# cohere answers 422 INVALID_TOOL_GENERATION now and then; a fresh try usually works
RETRY_ON = frozenset({422, 500, 502, 503, 504})
RETRIES_PER_KEY = 2
# trial keys are limited per minute: wait the window out a couple of times before giving up
COOLDOWN_S = 35.0
ROUNDS = 3
# a hung request must fail fast and be retried, never wait for minutes
REQUEST_TIMEOUT_S = 75.0
TRANSIENT = (httpx.TransportError, ModelAPIError)
SETTINGS = ModelSettings(timeout=REQUEST_TIMEOUT_S)

ModelFactory = Callable[[str, str], Model]


class LlmError(RuntimeError):
    pass


class ContextTooLargeError(LlmError):
    pass


@dataclass(frozen=True, slots=True)
class AgentRun[T]:
    output: T | None
    input_tokens: int
    output_tokens: int
    key_fp: str = ""
    latency_ns: int = 0


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
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._ledger, self._clock, self._model = ledger, clock, model_name
        self._keys = list(keys)
        self._spent: set[str] = set()
        self._rounds = ROUNDS
        self._factory, self._replay, self._emit, self._sleep = factory, replay, emit, sleep

    def extract[T: BaseModel](
        self, task: str, output: type[T], text: str, parent: str | None = None
    ) -> T:
        data = wrap_data(text)
        if len(data.encode()) > MAX_CONTEXT_BYTES:
            raise ContextTooLargeError(f"{task}: {len(data.encode())} bytes over the context cap")
        request_hash = self.request_hash(task, output, text)
        start = self._clock.ns()

        # replay and the ledger answer for free; the model is only asked once per text
        body = self.recall(request_hash)
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
        result, fp = self._across_keys(task, lambda key: self._run(task, output, data, key))
        latency = self._clock.ns() - start
        usage = result.usage
        self.remember(
            request_hash,
            task,
            result.output.model_dump_json().encode(),
            fp,
            usage.input_tokens,
            usage.output_tokens,
            latency,
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

    def recall(self, request_hash: str) -> bytes | None:
        # replay bundles and the ledger answer for free
        body = self._replay.get(request_hash) if self._replay is not None else None
        return body or self._ledger.llm_body(request_hash)

    def remember(
        self,
        request_hash: str,
        task: str,
        body: bytes,
        key_fp: str,
        input_tokens: int,
        output_tokens: int,
        latency_ns: int,
    ) -> None:
        self._ledger.record_llm(
            LlmCall(
                request_hash=request_hash,
                model=self._model,
                task=task,
                body_sha256=self._ledger.blobs.put(body),
                key_fp=key_fp,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ns=latency_ns,
                created_at=self._clock.now(),
            )
        )

    def _across_keys[R](self, task: str, attempt: Callable[[SecretStr], R]) -> tuple[R, str]:
        for round_ in range(self._rounds):
            found = self._one_round(task, attempt)
            if found is not None:
                return found
            # only rate limits are worth waiting for; anything else already moved on to the next key
            if not self._spent or round_ == self._rounds - 1:
                break
            self._sleep(COOLDOWN_S)
            self._spent.clear()
        # a limit that never lifted is probably a monthly cap: later calls fail fast, not wait again
        if self._spent:
            self._rounds = 1
        self._spent.clear()
        raise LlmError(f"{task}: every Cohere key is rate limited or failing")

    def _one_round[R](self, task: str, attempt: Callable[[SecretStr], R]) -> tuple[R, str] | None:
        for key in self._keys:
            fp = fingerprint(key.get_secret_value())
            if fp in self._spent:
                continue
            try:
                return attempt(key), fp
            except ModelHTTPError as exc:
                # a rate limit sets the key aside until the next round; a stubborn transient
                # error just moves on to the next key; anything else is a real failure
                if exc.status_code in ROTATE_ON:
                    self._spent.add(fp)
                    continue
                if exc.status_code in RETRY_ON:
                    continue
                raise LlmError(f"{task}: model error {exc.status_code}") from None
            except UnexpectedModelBehavior as exc:
                raise LlmError(f"{task}: output failed validation") from exc
            except TRANSIENT:
                # a stalled or dropped connection counts against this key; the next key gets a go
                continue
        return None

    def run_agent[T: BaseModel](
        self,
        task: str,
        output: type[T],
        system: str,
        brief: str,
        tools: Sequence[Tool],
        limits: UsageLimits,
        parent: str | None = None,
    ) -> AgentRun[T]:
        run = self.run_agent_or_text(
            task, output, system, brief, tools, limits, parent, text_ok=False
        )
        value = run.output if isinstance(run.output, output) else None
        return AgentRun(value, run.input_tokens, run.output_tokens, run.key_fp, run.latency_ns)

    def run_agent_or_text[T: BaseModel](
        self,
        task: str,
        output: type[T],
        system: str,
        brief: str,
        tools: Sequence[Tool],
        limits: UsageLimits,
        parent: str | None = None,
        *,
        text_ok: bool = True,
    ) -> AgentRun[T | str]:
        start = self._clock.ns()

        def attempt(key: SecretStr) -> AgentRun[T | str]:
            return self._agent_attempt(output, system, brief, tools, limits, key, text_ok=text_ok)

        run, fp = self._across_keys(task, attempt)
        latency = self._clock.ns() - start
        self._report(
            task, "agent", fp, run.input_tokens, run.output_tokens, latency, parent, cached=False
        )
        return replace(run, key_fp=fp, latency_ns=latency)

    def _agent_attempt[T: BaseModel](
        self,
        output: type[T],
        system: str,
        brief: str,
        tools: Sequence[Tool],
        limits: UsageLimits,
        key: SecretStr,
        *,
        text_ok: bool = False,
    ) -> AgentRun[T | str]:
        tries = 0
        # some models answer in prose instead of calling the output tool; a caller may accept that
        kinds: list[object] = [ToolOutput(output), str] if text_ok else [ToolOutput(output)]
        while True:
            agent = Agent(
                self._factory(self._model, key.get_secret_value()),
                output_type=kinds,
                instructions=system,
                tools=list(tools),
                retries=1,
                model_settings=SETTINGS,
            )
            try:
                done = agent.run_sync(brief, usage_limits=limits)
                return AgentRun(done.output, done.usage.input_tokens, done.usage.output_tokens)
            except (UsageLimitExceeded, UnexpectedModelBehavior):
                # whatever the tools gathered before the loop ended is still in the book
                return AgentRun(None, 0, 0)
            except ModelHTTPError as exc:
                if exc.status_code not in RETRY_ON or tries >= RETRIES_PER_KEY:
                    raise
                tries += 1
            except TRANSIENT:
                if tries >= RETRIES_PER_KEY:
                    raise
                tries += 1

    def _run[T: BaseModel](
        self, task: str, output: type[T], data: str, key: SecretStr
    ) -> AgentRunResult[T]:
        attempt = 0
        while True:
            agent = Agent(
                self._factory(self._model, key.get_secret_value()),
                output_type=ToolOutput(output),
                instructions=instructions(task),
                retries=1,
                model_settings=SETTINGS,
            )
            try:
                return agent.run_sync(data)
            except ModelHTTPError as exc:
                if exc.status_code not in RETRY_ON or attempt >= RETRIES_PER_KEY:
                    raise
                attempt += 1
            except TRANSIENT:
                if attempt >= RETRIES_PER_KEY:
                    raise
                attempt += 1

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
