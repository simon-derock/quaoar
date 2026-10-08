# spec: SPEC-LT-01, SPEC-LT-02, SPEC-LT-03, SPEC-LT-04
from datetime import date

from pydantic import JsonValue

from quaoar.checks.litigation import litigation_check, matter_date
from quaoar.domain.claims import DisclosedCaseClaim, PromoterClaim
from quaoar.domain.findings import Status
from quaoar.guard.wording import banned_terms
from quaoar.scoring.litigation_rules import litigation_signals
from tests.unit.checks.test_vendor import FakeSearch

KANOON = {
    "title": "Trafiksol Its Technologies Limited vs Sebi & Another on 24 January, 2025",
    "link": "https://indiankanoon.org/doc/180391242/",
    "snippet": "appeal against the order",
}
SEBI = {
    "title": "Order in the matter of Trafiksol ITS Technologies Ltd",
    "link": "https://www.sebi.gov.in/enforcement/orders/dec-2024/order-in-the-matter-of-trafiksol_9.html",
    "snippet": "case ZD0905242971733",
}
OTHER = {
    "title": "Some Other Company vs SEBI",
    "link": "https://indiankanoon.org/doc/1/",
    "snippet": "",
}
OFFSITE = {
    "title": "Trafiksol ITS Technologies news",
    "link": "https://news.example/x",
    "snippet": "",
}
ISSUER = "TRAFIKSOL ITS TECHNOLOGIES LIMITED"
PROMOTERS = [
    PromoterClaim(page=172, name=n)
    for n in ("Person One", "Person Two", "Person Three", "Person Four")
]


def body(*items: dict[str, str]) -> dict[str, JsonValue]:
    return {"organic_results": [dict(i) for i in items]}


def check(*items: dict[str, str], disclosed: list[DisclosedCaseClaim] | None = None):  # type: ignore[no-untyped-def]
    search = FakeSearch({"duckduckgo": body(*items)})
    return litigation_check(ISSUER, 1, disclosed or [], PROMOTERS, search), search


def test_dates_come_from_the_title_or_the_sebi_url() -> None:
    assert matter_date(KANOON["link"], KANOON["title"]) == date(2025, 1, 24)
    assert matter_date(SEBI["link"], SEBI["title"]) == date(2024, 12, 1)


def test_undisclosed_matter_before_the_cutoff_does_not_match() -> None:
    found, _ = check(SEBI, OTHER, OFFSITE)
    (signal,) = litigation_signals(found, date(2025, 3, 1))
    assert signal.status is Status.INCONSISTENT
    assert "worth a closer look" in signal.text
    assert banned_terms(signal.text) == []


def test_a_matter_whose_case_reference_is_disclosed_is_not_extra() -> None:
    disclosed = [DisclosedCaseClaim(page=271, party=ISSUER, case_ref="ZD0905242971733")]
    found, _ = check(SEBI, disclosed=disclosed)
    (signal,) = litigation_signals(found, date(2025, 3, 1))
    assert signal.status is Status.CONSISTENT


def test_matters_after_the_cutoff_or_undated_are_ignored_in_point_in_time_mode() -> None:
    found, _ = check(KANOON)
    assert litigation_signals(found, date(2024, 9, 3))[0].status is Status.CONSISTENT
    assert litigation_signals(found, None)[0].status is Status.INCONSISTENT


def test_only_the_issuer_and_three_promoters_are_searched_by_name() -> None:
    found, search = check()
    assert len(search.calls) == 4
    assert found.subjects[0] == ISSUER
    assert all("site:sebi.gov.in" in str(c[1]["q"]) for c in search.calls)
    assert found.subjects[1:] == ["Person One", "Person Two", "Person Three"]
