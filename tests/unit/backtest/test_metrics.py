# spec: SPEC-BT-04
import pytest
from hypothesis import given
from hypothesis import strategies as st

from quaoar.backtest.metrics import CaseResult, describe, from_card, summarize, wilson
from quaoar.domain.findings import Signal, Status
from quaoar.scoring.card import build_card


def case(role: str, flagged: bool) -> CaseResult:
    return CaseResult("x", role, flagged, 5, int(flagged), 1, 3)


def test_wilson_matches_known_values() -> None:
    low, high = wilson(0, 3)
    assert low == 0.0
    assert high == pytest.approx(0.562, abs=0.002)
    low, high = wilson(1, 1)
    assert low == pytest.approx(0.207, abs=0.002)
    assert high == 1.0
    assert wilson(0, 0) == (0.0, 1.0)


@given(st.integers(0, 60), st.integers(1, 60))
def test_interval_always_contains_the_observed_rate_and_stays_in_range(
    hits: int, total: int
) -> None:
    hits = min(hits, total)
    low, high = wilson(hits, total)
    assert 0.0 <= low <= hits / total <= high <= 1.0


def test_summary_counts_flagged_cases_by_role() -> None:
    cases = [
        case("positive", True),
        case("control", False),
        case("control", False),
        case("control", True),
    ]
    summary = summarize(cases)
    assert (summary.positives.hits, summary.positives.total) == (1, 1)
    assert (summary.controls.hits, summary.controls.total) == (1, 3)
    assert describe(summary.controls, "controls").startswith(
        "controls flagged: 1 of 3 (95% interval"
    )


def test_a_case_is_flagged_by_any_line_that_did_not_match() -> None:
    def sig(s: Status) -> Signal:
        return Signal(check="vendor", rule="R", subject="V", status=s, text="t")

    flagged = from_card(
        "a", "control", build_card("q", "A", [sig(Status.CONSISTENT), sig(Status.INCONSISTENT)]), 4
    )
    quiet = from_card(
        "b", "control", build_card("q", "B", [sig(Status.CONSISTENT), sig(Status.UNVERIFIED)]), 2
    )
    assert (flagged.flagged, quiet.flagged) == (True, False)
    assert quiet.unverified == 1
