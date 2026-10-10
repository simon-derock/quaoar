# spec: SPEC-VX-01, SPEC-VX-03, SPEC-VX-04, SPEC-VX-05, SPEC-AG-04, SPEC-SC-05
from collections.abc import Mapping
from datetime import date

from pydantic import JsonValue

from quaoar.checks.book import EvidenceBook, Goal, Hit, ToolCall
from quaoar.checks.vendor import vendor_xray
from quaoar.domain.claims import QuoteClaim
from quaoar.domain.findings import Status
from quaoar.guard.wording import banned_terms
from quaoar.scoring.rules import vendor_signals
from quaoar.serp.client import SerpResult
from tests.unit.checks.test_registry import ELSEWHERE, INSTA, ZAUBA

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
    (engine1, params1), (engine2, params2), (engine3, params3) = search.calls
    assert engine1 == "duckduckgo"
    assert str(params1["q"]).startswith('"OASIS CORPCARE" (site:zaubacorp.com')
    assert (engine2, params2["q"]) == ("google_maps", "OASIS CORPCARE PRIVATE LIMITED Mumbai")
    assert engine3 == "duckduckgo"
    assert str(params3["q"]).startswith('"OASIS CORPCARE" (site:sebi.gov.in')


def test_absence_is_never_a_mismatch() -> None:
    result = signals(FakeSearch({}))
    assert Status.INCONSISTENT not in result.values()
    assert {result[r] for r in ("VX-02", "VX-03", "VX-04", "VX-05")} == {Status.UNVERIFIED}


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


LEGAL_HIT = {
    "title": "Order in the matter of Oasis Corpcare Private Limited",
    "link": "https://www.sebi.gov.in/enforcement/orders/dec-2024/order-oasis_1.html",
    "snippet": "SEBI order",
}


class LegalRouted(FakeSearch):
    def query(self, engine, params, parent=None):  # type: ignore[no-untyped-def]
        legal = "site:sebi.gov.in" in str(params.get("q", ""))
        body = registry_body(LEGAL_HIT) if legal else self.bodies.get(engine, {})
        self.bodies = {**self.bodies, engine: body}
        return super().query(engine, params, parent)


def test_a_legal_page_naming_the_vendor_before_the_cutoff_does_not_match() -> None:
    search = LegalRouted({"duckduckgo": {}, "google_maps": maps_body()})
    found = vendor_xray(QUOTE, search)
    signal = {s.rule: s for s in vendor_signals(found, date(2025, 1, 1))}["VX-06"]
    assert signal.status is Status.INCONSISTENT
    assert "worth a closer look" in signal.text
    assert banned_terms(signal.text) == []


def test_a_legal_page_dated_after_the_cutoff_is_ignored_in_point_in_time_mode() -> None:
    found = vendor_xray(QUOTE, LegalRouted({"duckduckgo": {}, "google_maps": maps_body()}))
    assert {s.rule: s.status for s in vendor_signals(found, date(2024, 9, 3))}[
        "VX-06"
    ] is Status.CONSISTENT


class FakeInvestigator:
    def __init__(self, hits: list[Hit]) -> None:
        self.hits, self.goals = hits, []  # type: ignore[var-annotated]

    def run(self, goal: Goal, parent: str | None = None) -> EvidenceBook:
        self.goals.append(goal)
        return EvidenceBook(
            hits=self.hits, calls=[ToolCall(tool="search_maps", args={"terms": "x"}, why="gap")]
        )


def maps_hit() -> Hit:
    result = SerpResult("m" * 20, "google_maps", "ok", "sid-m", {}, 1, False, 1)
    return Hit(
        "search_maps",
        result,
        {"title": "Oasis Corpcare Pvt Ltd", "address": "Shop 4, Mira Road, Mumbai"},
    )


def test_the_agent_runs_only_when_a_gap_remains_and_fills_it() -> None:
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": {}})
    agent = FakeInvestigator([maps_hit()])
    found = vendor_xray(QUOTE, search, investigator=agent)
    assert [g.gaps for g in agent.goals] == [("maps",)]
    assert found.maps.found
    assert found.agent_searches == 1
    assert {s.rule: s.status for s in vendor_signals(found, date(2024, 9, 3))}[
        "VX-05"
    ] is Status.CONSISTENT


def test_with_no_gap_the_agent_is_never_called() -> None:
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": maps_body()})
    agent = FakeInvestigator([])
    vendor_xray(QUOTE, search, investigator=agent)
    assert agent.goals == []


def test_the_brief_carries_known_facts_and_the_queries_already_done() -> None:
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA), "google_maps": {}})
    agent = FakeInvestigator([])
    vendor_xray(QUOTE, search, investigator=agent)
    goal = agent.goals[0]
    assert goal.kind == "vendor"
    assert goal.gaps == ("registry", "maps")
    assert any(d.startswith("registry:") for d in goal.done)
    assert goal.known["city"] == "Mumbai"
    assert "search_maps" in goal.tools


def test_agent_evidence_off_the_registry_sites_cannot_create_registry_facts() -> None:
    result = SerpResult("r" * 20, "google", "ok", "sid-r", {}, 1, False, 1)
    fake = Hit("search_web", result, dict(ELSEWHERE))
    found = vendor_xray(QUOTE, FakeSearch({}), investigator=FakeInvestigator([fake]))
    assert found.registry.paid_up_paise is None


NO_FORM = QuoteClaim(
    page=89,
    vendor="Krishna Enterprises",
    item="goods",
    amount_text="46.00",
    unit_text="Lakhs",
    quote_date_text="",
)
SAME_NAME_COMPANY = {
    "title": "KRISHNA ENTERPRISES PRIVATE LIMITED - ZaubaCorp",
    "link": "https://www.zaubacorp.com/company/KRISHNA-ENTERPRISES/U16000DL1989PTC037800",
    "snippet": "paid up capital is ₹15,000.00 The current status of the company is Active.",
}


def test_a_vendor_with_no_company_form_is_never_matched_to_a_same_named_company() -> None:
    own: dict[str, JsonValue] = {
        "local_results": [{"title": "Krishna Enterprises", "address": "Shop 4, Mira Road, Mumbai"}]
    }
    search = FakeSearch({"duckduckgo": registry_body(SAME_NAME_COMPANY), "google_maps": own})
    found = vendor_xray(NO_FORM, search)
    assert [engine for engine, _ in search.calls] == ["google_maps"]
    assert not found.registered
    by_rule = {s.rule: s for s in vendor_signals(found, date(2024, 7, 18))}
    assert by_rule["VX-02"].status is Status.UNVERIFIED
    assert "no company form" in by_rule["VX-02"].text
    assert {"VX-03", "VX-04", "VX-06"}.isdisjoint(by_rule)
    # a name alone doesn't confirm a bare trade name is the vendor, so the listing is shown but not counted
    assert by_rule["VX-05"].status is Status.UNVERIFIED
    assert "name alone doesn't confirm" in by_rule["VX-05"].text
    assert by_rule["VX-05"].evidence


def test_a_name_match_at_a_plainly_foreign_address_is_a_different_business() -> None:
    # "M/s Vraj Construction" matched a Pennsylvania company on Maps and was reported permanently closed
    from quaoar.checks.vendor import best_place

    abroad = {
        "title": "VRAJ Construction",
        "address": "964 Station Ave, Bensalem, PA 19020",
        "open_state": "Permanently closed",
    }
    home = {"title": "Vraj Construction", "address": "Ring Road, Surat, Gujarat 395002"}
    assert best_place("M/s Vraj Construction", [abroad]) is None
    assert best_place("M/s Vraj Construction", [abroad, home]) is home
    # an address without a country or a PIN code is still accepted: only plain foreign ones are dropped
    local = {"title": "Vraj Construction", "address": "Raiya Road, Rajkot"}
    assert best_place("M/s Vraj Construction", [local]) is local
