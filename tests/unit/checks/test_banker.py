# spec: SPEC-BK-01, SPEC-BK-03, SPEC-BK-04, SPEC-BK-05
from datetime import date

from pydantic import JsonValue

from quaoar.checks.banker import banker_check, is_sebi_order, order_month
from quaoar.domain.claims import LeadManagerClaim, PastIssueClaim
from quaoar.domain.findings import Status
from quaoar.guard.wording import banned_terms
from quaoar.scoring.banker_rules import banker_signals
from tests.unit.checks.test_vendor import FakeSearch

ORDER = {
    "title": "Final Order in the matter of First Overseas Capital Limited",
    "link": "https://www.sebi.gov.in/enforcement/orders/oct-2025/final-order-in-the-matter-of-first-overseas-capital-limited_1.html",
    "snippet": "SEBI order",
}
SYN = {
    "title": "Interim Order in the matter of Synoptics Technologies Limited",
    "link": "https://www.sebi.gov.in/enforcement/orders/may-2025/interim-order-synoptics_2.html",
    "snippet": "SEBI order",
}
NEWS = {
    "title": "First Overseas Capital shares",
    "link": "https://watchoutinvestors.com/x",
    "snippet": "",
}
BANKER = LeadManagerClaim(page=80, name="First Overseas Capital Limited")
PAST = [
    PastIssueClaim(page=292, issuer="Synoptics Technologies Limited"),
    PastIssueClaim(page=292, issuer="Quiet Industries Limited"),
]


def body(*items: dict[str, str]) -> dict[str, JsonValue]:
    return {"organic_results": [dict(i) for i in items]}


class RoutedSearch(FakeSearch):
    def query(self, engine, params, parent=None):  # type: ignore[no-untyped-def]
        q = str(params["q"])
        key = "banker" if "First Overseas" in q else "syn" if "Synoptics" in q else "none"
        self.bodies = {
            "duckduckgo": {"banker": body(ORDER, NEWS), "syn": body(SYN), "none": body(NEWS)}[key]
        }
        return super().query(engine, params, parent)


def test_order_urls_and_months_are_read_from_sebi_paths() -> None:
    assert is_sebi_order(ORDER["link"])
    assert not is_sebi_order(NEWS["link"])
    assert not is_sebi_order("https://sebi.gov.in.evil.example/enforcement/orders/oct-2025/x.html")
    assert order_month(ORDER["link"]) == date(2025, 10, 1)


def test_banker_with_orders_and_flagged_past_issuer_does_not_match() -> None:
    f = banker_check(BANKER, PAST, RoutedSearch({}))
    sig = {s.rule: s for s in banker_signals(f, date(2025, 12, 1))}
    assert sig["BK-04"].status is Status.INCONSISTENT
    assert "Oct 2025" in sig["BK-04"].text
    assert sig["BK-05"].status is Status.INCONSISTENT
    assert "Synoptics Technologies Limited" in sig["BK-05"].text
    assert sig["BK-05"].observed == "1 of 2 past issues"


def test_point_in_time_ignores_orders_published_after_the_cutoff() -> None:
    f = banker_check(BANKER, PAST, RoutedSearch({}))
    sig = {s.rule: s for s in banker_signals(f, date(2025, 1, 15))}
    assert sig["BK-04"].status is Status.CONSISTENT
    assert sig["BK-05"].status is Status.CONSISTENT
    assert all(s.pit_ok for s in sig.values())


def test_missing_past_issues_table_is_unverified_and_nothing_found_is_consistent() -> None:
    f = banker_check(BANKER, [], FakeSearch({"duckduckgo": body(NEWS)}))
    sig = {s.rule: s.status for s in banker_signals(f, None)}
    assert sig == {"BK-04": Status.CONSISTENT, "BK-05": Status.UNVERIFIED}


def test_past_issuers_are_deduplicated_and_capped() -> None:
    many = [PastIssueClaim(page=1, issuer=f"Issuer {chr(65 + i)} Limited") for i in range(9)] * 2
    search = FakeSearch({"duckduckgo": body(NEWS)})
    f = banker_check(BANKER, many, search)
    assert len(f.past_issuers) == 5
    assert len(search.calls) == 6


def test_signal_text_is_neutral() -> None:
    f = banker_check(BANKER, PAST, RoutedSearch({}))
    assert all(banned_terms(s.text) == [] for s in banker_signals(f, date(2025, 12, 1)))


def test_a_single_past_issuer_reads_naturally() -> None:
    f = banker_check(BANKER, PAST[1:], FakeSearch({"duckduckgo": body(NEWS)}))
    sig = {s.rule: s for s in banker_signals(f, None)}
    assert "naming past issuer of" in sig["BK-05"].text
