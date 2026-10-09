# what an investigation leaves behind: every hit it saw, in order, with the search that produced it
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

from quaoar.serp.client import SerpResult


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool: str
    args: dict[str, str]
    why: str = ""


class Handoff(BaseModel):
    model_config = ConfigDict(frozen=True)

    resolved: list[str] = []
    unresolved: list[str] = []
    note: str = ""


@dataclass(frozen=True, slots=True)
class Hit:
    tool: str
    result: SerpResult
    item: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Goal:
    kind: str
    entity: str
    known: dict[str, str]
    gaps: tuple[str, ...]
    done: tuple[str, ...]
    tools: tuple[str, ...]


@dataclass(slots=True)
class EvidenceBook:
    hits: list[Hit] = field(default_factory=list)
    calls: list[ToolCall] = field(default_factory=list)
    credits: int = 0
    steps: int = 0
    handoff: Handoff | None = None

    def of(self, tool: str) -> list[Hit]:
        return [h for h in self.hits if h.tool == tool]

    def items(self, tool: str) -> Sequence[dict[str, JsonValue]]:
        return [h.item for h in self.of(tool)]


class Investigator(Protocol):
    def run(self, goal: Goal, parent: str | None = None) -> EvidenceBook: ...
