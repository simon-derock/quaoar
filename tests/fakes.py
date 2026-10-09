# test doubles shared across suites: a clock that only moves when told to
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


class FixedClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
        self._ns = 0

    def now(self) -> datetime:
        return self._now

    def ns(self) -> int:
        self._ns += 1_000
        return self._ns

    def advance(self, **delta: float) -> None:
        self._now += timedelta(**delta)


# a scripted model for agent tests: replays tool calls in order, then answers with the final tool
def scripted_model(
    steps: Sequence[tuple[str, Mapping[str, object]]], final: Mapping[str, object] | None = None
) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        turn = sum(isinstance(m, ModelResponse) for m in messages)
        if turn < len(steps):
            name, args = steps[turn]
            return ModelResponse(parts=[ToolCallPart(name, dict(args))])
        answer = final if final is not None else {"resolved": [], "unresolved": [], "note": "done"}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, dict(answer))])

    return FunctionModel(respond)
