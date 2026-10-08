# spec: SPEC-SC-04, SPEC-SC-05
from quaoar.domain.findings import Signal, Status
from quaoar.guard.wording import banned_terms
from quaoar.scoring.card import DISCLAIMER, build_card, card_lines, headline


def sig(rule: str, status: Status) -> Signal:
    return Signal(check="vendor", rule=rule, subject="V", status=status, text=f"{rule} text")


def test_card_counts_and_lists_only_mismatches_on_top() -> None:
    signals = [
        sig("VX-02", Status.CONSISTENT),
        sig("VX-03", Status.INCONSISTENT),
        sig("VX-04", Status.CONSISTENT),
        sig("VX-05", Status.UNVERIFIED),
        sig("XX-01", Status.NOT_APPLICABLE),
    ]
    card = build_card("q1", "DEMO LIMITED", signals)
    assert (card.consistent, card.inconsistent, card.unverified) == (2, 1, 1)
    assert [s.rule for s in card.top] == ["VX-03"]
    assert len(card.signals) == 4
    assert headline(card) == "2 of 4 check out · 1 don't match · 1 couldn't find"


def test_card_has_no_score_and_always_the_disclaimer() -> None:
    card = build_card("q1", "DEMO LIMITED", [sig("VX-03", Status.INCONSISTENT)])
    assert "score" not in card.model_dump()
    lines = card_lines(card)
    assert lines[-1] == DISCLAIMER
    assert all(banned_terms(line) == [] for line in lines)


def test_top_is_capped_at_three() -> None:
    card = build_card("q1", "X", [sig(f"R-{i}", Status.INCONSISTENT) for i in range(5)])
    assert len(card.top) == 3
