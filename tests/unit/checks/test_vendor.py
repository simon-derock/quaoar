# spec: SPEC-VX-01, SPEC-VX-03, SPEC-VX-04, SPEC-VX-05, SPEC-AG-04, SPEC-SC-05
from collections.abc import Mapping
from datetime import date

from pydantic import JsonValue

from quaoar.checks.vendor import vendor_xray
from quaoar.domain.claims import QuoteClaim
from quaoar.domain.findings import Status
from quaoar.guard.wording import banned_terms
from quaoar.scoring.rules import vendor_signals
from quaoar.serp.client import SerpResult
from tests.unit.checks.test_registry import INSTA, ZAUBA

QUOTE = QuoteClaim(
    page=89,
    vendor="OASIS CORPCARE PRIVATE LIMITED",
    item="Computer Application Software with IPR",
    amount_text="1,770.00",
    unit_text="Lakhs",
    quote_date_text="May 16, 2024",
)


class FakeSearch:
    def __init__(self, bodies: Mapping[str, dict[str, JsonValue]]) -> None:
        self.bodies = bodies
        self.calls: list[tuple[str, dict[str, object]]] = []

    def query(
        self, engine: str, params: Mapping[str, object], parent: str | None = None
    ) -> SerpResult:
        self.calls.append((engine, dict(params)))
        body = self.bodies.get(engine, {})
        return SerpResult(
            f"{engine}-hash-0000000000", engine, "ok", f"sid-{engine}", body, 1, False, 1
        )


def registry_body(*items: Mapping[str, str]) -> dict[str, JsonValue]:
    return {"organic_results": [dict(i) for i in items]}


def maps_body(**place: JsonValue) -> dict[str, JsonValue]:
    return {
        "local_results": [
            {"title": "Oasis Corpcare Pvt Ltd", "address": "Shop 4, Mira Road, Mumbai", **place}
        ]
    }


def signals(search: FakeSearch, cutoff: date | None = date(2024, 9, 3)) -> dict[str, Status]:
    findings = vendor_xray(QUOTE, search)
    return {s.rule: s.status for s in vendor_signals(findings, cutoff)}


def test_the_trafiksol_pattern_is_flagged_on_capital() -> None:
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": maps_body()})
    findings = vendor_xray(QUOTE, search)
    found = {s.rule: s for s in vendor_signals(findings, date(2024, 9, 3))}
    assert findings.quote_paise == 17_70_00_000_00
    assert found["VX-03"].status is Status.INCONSISTENT
    assert "1,770 times" in found["VX-03"].text
    assert [e.url for e in found["VX-03"].evidence] == [INSTA["link"]]
    assert [e.url for e in found["VX-02"].evidence] == [ZAUBA["link"]]
    assert found["VX-02"].status is Status.CONSISTENT
    assert found["VX-04"].status is Status.CONSISTENT
    assert found["VX-05"].status is Status.CONSISTENT


def test_searches_use_duckduckgo_for_sites_and_the_registry_city_for_maps() -> None:
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": maps_body()})
    vendor_xray(QUOTE, search)
    (engine1, params1), (engine2, params2) = search.calls
    assert engine1 == "duckduckgo"
    assert str(params1["q"]).startswith('"OASIS CORPCARE" (site:zaubacorp.com')
    assert (engine2, params2["q"]) == ("google_maps", "OASIS CORPCARE PRIVATE LIMITED Mumbai")


def test_absence_is_never_a_mismatch() -> None:
    assert set(signals(FakeSearch({})).values()) == {Status.UNVERIFIED}


def test_struck_off_or_closed_vendors_do_not_match() -> None:
    struck = dict(
        INSTA,
        snippet="The current status of the company is Strike Off. paid up capital is ₹5,00,00,000.00",
    )
    closed = maps_body(open_state="Permanently closed")
    result = signals(FakeSearch({"duckduckgo": registry_body(struck), "google_maps": closed}))
    assert result["VX-04"] is Status.INCONSISTENT
    assert result["VX-05"] is Status.INCONSISTENT
    assert result["VX-03"] is Status.CONSISTENT


def test_a_stale_balance_sheet_does_not_match() -> None:
    stale = dict(
        INSTA,
        snippet="balance sheet as on 31 March 2019. The current status of the company is Active.",
    )
    assert signals(FakeSearch({"duckduckgo": registry_body(stale)}))["VX-04"] is Status.INCONSISTENT


def test_maps_shows_area_and_city_only() -> None:
    search = FakeSearch({"duckduckgo": registry_body(INSTA), "google_maps": maps_body()})
    findings = vendor_xray(QUOTE, search)
    assert findings.maps.city_area == "Mira Road, Mumbai"


def test_every_signal_text_passes_the_wording_guard() -> None:
    for bodies in ({}, {"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": maps_body()}):
        for signal in vendor_signals(vendor_xray(QUOTE, FakeSearch(bodies)), date(2024, 9, 3)):
            assert banned_terms(signal.text) == []
