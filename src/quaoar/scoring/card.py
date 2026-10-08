# the card: plain counts, the three findings worth a closer look, and the disclaimer
from pydantic import BaseModel, ConfigDict

from quaoar.domain.findings import Signal, Status
from quaoar.scoring.rules import RULESET_VERSION

DISCLAIMER = "Facts with sources. Not investment advice."
TOP = 3
MARKS = {
    Status.CONSISTENT: "checks out",
    Status.INCONSISTENT: "doesn't match",
    Status.UNVERIFIED: "couldn't find",
    Status.NOT_APPLICABLE: "not applicable",
}


class Card(BaseModel):
    model_config = ConfigDict(frozen=True)

    scan_id: str
    company: str
    consistent: int
    inconsistent: int
    unverified: int
    top: tuple[Signal, ...]
    signals: tuple[Signal, ...]
    ruleset: str = RULESET_VERSION
    disclaimer: str = DISCLAIMER


def build_card(scan_id: str, company: str, signals: list[Signal]) -> Card:
    counted = [s for s in signals if s.status is not Status.NOT_APPLICABLE]

    # no overall score: the card only counts and points at what didn't match
    return Card(
        scan_id=scan_id,
        company=company,
        consistent=sum(s.status is Status.CONSISTENT for s in counted),
        inconsistent=sum(s.status is Status.INCONSISTENT for s in counted),
        unverified=sum(s.status is Status.UNVERIFIED for s in counted),
        top=tuple(s for s in counted if s.status is Status.INCONSISTENT)[:TOP],
        signals=tuple(counted),
    )


def headline(card: Card) -> str:
    total = card.consistent + card.inconsistent + card.unverified
    return (
        f"{card.consistent} of {total} check out · {card.inconsistent} don't match · "
        f"{card.unverified} couldn't find"
    )


def card_lines(card: Card) -> list[str]:
    lines = [f"QUAOAR · {card.company}", headline(card), ""]
    for number, signal in enumerate(card.signals, start=1):
        lines.append(f"{number:>2}. [{MARKS[signal.status]}] {signal.text}")
    lines += ["", card.disclaimer]
    return lines
