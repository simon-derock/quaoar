# what a guard reports: which guard and rule fired and how often, never the text it caught
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GuardHit:
    guard: str
    rule: str
    count: int


@dataclass(frozen=True, slots=True)
class Cleaned:
    text: str
    hits: tuple[GuardHit, ...]
