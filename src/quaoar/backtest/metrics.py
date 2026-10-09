# evaluation maths: a case is flagged when any line did not match; rates always carry an interval
import math
from dataclasses import dataclass

from quaoar.scoring.card import Card

Z95 = 1.96


@dataclass(frozen=True, slots=True)
class CaseResult:
    name: str
    role: str
    flagged: bool
    consistent: int
    inconsistent: int
    unverified: int
    credits: int


@dataclass(frozen=True, slots=True)
class Rate:
    hits: int
    total: int
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class Summary:
    positives: Rate
    controls: Rate


def wilson(hits: int, total: int, z: float = Z95) -> tuple[float, float]:
    # 95% interval for a proportion that stays honest at tiny sample sizes
    if total == 0:
        return 0.0, 1.0
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    # the exact bounds at 0 hits and at all hits are 0 and 1; rounding must not nudge them
    low = 0.0 if hits == 0 else max(0.0, centre - half)
    high = 1.0 if hits == total else min(1.0, centre + half)
    return low, high


def from_card(name: str, role: str, card: Card, spent: int) -> CaseResult:
    return CaseResult(
        name,
        role,
        card.inconsistent > 0,
        card.consistent,
        card.inconsistent,
        card.unverified,
        spent,
    )


def rate(cases: list[CaseResult], role: str) -> Rate:
    chosen = [c for c in cases if c.role == role]
    hits = sum(c.flagged for c in chosen)
    low, high = wilson(hits, len(chosen))
    return Rate(hits, len(chosen), low, high)


def summarize(cases: list[CaseResult]) -> Summary:
    return Summary(rate(cases, "positive"), rate(cases, "control"))


def describe(rate_: Rate, label: str) -> str:
    return f"{label} flagged: {rate_.hits} of {rate_.total} (95% interval {rate_.low:.0%} to {rate_.high:.0%})"
