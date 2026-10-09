# the investigator: runs the ReAct loop for one goal and returns the evidence it gathered
from dataclasses import dataclass

from pydantic import BaseModel
from pydantic_ai.usage import UsageLimits

from quaoar.agent.prompts import AGENT_PROMPT_VERSION, SYSTEM, build_brief
from quaoar.agent.tools import Toolbox
from quaoar.checks.base import SearchPort
from quaoar.checks.book import EvidenceBook, Goal, Handoff, ToolCall
from quaoar.domain.ids import canonical_json, sha256_hex
from quaoar.events import Emitter
from quaoar.llm.client import LlmClient, LlmError


class Trace(BaseModel):
    calls: list[ToolCall]
    handoff: Handoff | None


@dataclass(frozen=True, slots=True)
class Budget:
    max_credits: int = 6
    max_searches: int = 8
    # one model request per search plus the final answer, with a little slack
    extra_requests: int = 2


class AgentInvestigator:
    def __init__(
        self,
        llm: LlmClient,
        search: SearchPort,
        emit: Emitter | None = None,
        budget: Budget | None = None,
    ) -> None:
        self._llm, self._search, self._emit = llm, search, emit
        self._budget = budget or Budget()

    def run(self, goal: Goal, parent: str | None = None) -> EvidenceBook:
        book = EvidenceBook()
        toolbox = Toolbox(
            self._search, book, self._emit, parent,
            max_credits=self._budget.max_credits, max_searches=self._budget.max_searches,
        )  # fmt: skip
        brief = build_brief(goal, self._budget.max_credits, self._budget.max_searches)
        task = f"agent:{goal.kind}"
        key = sha256_hex(
            canonical_json(
                {"task": task, "prompt": AGENT_PROMPT_VERSION, "brief": sha256_hex(brief)}
            )
        )

        # an investigation that already ran is replayed from its recorded tool calls, with no model call
        recorded = self._llm.recall(key)
        if recorded is not None:
            trace = Trace.model_validate_json(recorded)
            for call in trace.calls:
                toolbox.dispatch(call)
            book.handoff = trace.handoff
            return book

        limits = UsageLimits(request_limit=self._budget.max_searches + self._budget.extra_requests)
        try:
            run = self._llm.run_agent(
                task, Handoff, SYSTEM, brief, toolbox.tools(goal.tools), limits, parent
            )
        except LlmError:
            # no model available: the fixed evidence already gathered still stands
            return book
        book.handoff = run.output
        trace = Trace(calls=book.calls, handoff=run.output)
        self._llm.remember(
            key,
            task,
            trace.model_dump_json().encode(),
            run.key_fp,
            run.input_tokens,
            run.output_tokens,
            run.latency_ns,
        )
        return book
