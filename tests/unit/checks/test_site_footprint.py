# spec: SPEC-SV-01, SPEC-SV-02, SPEC-SV-04, SPEC-HY-01, SPEC-AG-01
from datetime import date

from pydantic import JsonValue

from quaoar.checks.book import EvidenceBook, Goal, Hit, ToolCall
from quaoar.checks.footprint import footprint
from quaoar.checks.site import site_visit
from quaoar.domain.claims import PlaceClaim
from quaoar.domain.findings import Status
from quaoar.guard.wording import banned_terms
from quaoar.scoring.footprint_rules import footprint_signals
from quaoar.scoring.site_rules import site_signals
from quaoar.serp.client import SerpResult
from tests.unit.checks.test_vendor import FakeSearch

ISSUER = "BRIGHTWELL POLYMERS LIMITED"
FACTORY = PlaceClaim(page=75, role="factory", locality="MIDC Ranjangaon", city="Pune")
OFFICE = PlaceClaim(page=75, role="registered_office", locality="Sector 63", city="Noida")


def place(**kw: JsonValue) -> dict[str, JsonValue]:
    return {
        "local_results": [
            {"title": "Brightwell Polymers Ltd", "address": "MIDC, Pune", "type": "Factory", **kw}
        ]
    }


def test_a_matching_open_factory_checks_out() -> None:
    found = site_visit(ISSUER, FACTORY, FakeSearch({"google_maps": place()}))
    assert [(s.rule, s.status) for s in site_signals(found)] == [("SV-02", Status.CONSISTENT)]


def test_a_factory_listed_as_an_apartment_does_not_match() -> None:
    found = site_visit(
        ISSUER, FACTORY, FakeSearch({"google_maps": place(type="Apartment building")})
    )
    by_rule = {s.rule: s for s in site_signals(found)}
    assert by_rule["SV-04"].status is Status.INCONSISTENT
    assert "worth a closer look" in by_rule["SV-04"].text


def test_a_residential_type_is_not_held_against_a_registered_office() -> None:
    found = site_visit(ISSUER, OFFICE, FakeSearch({"google_maps": place(type="Housing society")}))
    assert {s.rule for s in site_signals(found)} == {"SV-02"}


def test_permanently_closed_and_missing_listings() -> None:
    closed = site_visit(
        ISSUER, FACTORY, FakeSearch({"google_maps": place(open_state="Permanently closed")})
    )
    assert site_signals(closed)[0].status is Status.INCONSISTENT
    missing = site_visit(ISSUER, FACTORY, FakeSearch({"google_maps": {}}))
    assert site_signals(missing)[0].status is Status.UNVERIFIED


class OneShot:
    def __init__(self) -> None:
        self.goals: list[Goal] = []

    def run(self, goal: Goal, parent: str | None = None) -> EvidenceBook:
        self.goals.append(goal)
        result = SerpResult("p" * 20, "google_maps", "ok", "sid", {}, 1, False, 1)
        item: dict[str, JsonValue] = {
            "title": "Brightwell Polymers Limited",
            "address": "MIDC, Pune",
            "type": "Factory",
        }
        return EvidenceBook(
            hits=[Hit("search_maps", result, item)],
            calls=[ToolCall(tool="search_maps", args={}, why="")],
        )


def test_the_agent_is_asked_only_when_the_fixed_query_found_nothing() -> None:
    agent = OneShot()
    found = site_visit(ISSUER, FACTORY, FakeSearch({"google_maps": {}}), investigator=agent)
    assert found.maps.found
    assert agent.goals[0].kind == "place"
    assert agent.goals[0].known["city"] == "Pune"
    seen = OneShot()
    site_visit(ISSUER, FACTORY, FakeSearch({"google_maps": place()}), investigator=seen)
    assert seen.goals == []


NEWS: dict[str, JsonValue] = {
    "news_results": [
        {
            "title": "Brightwell Polymers IPO opens on 12 Sept",
            "link": "https://n.example/1",
            "date": "09/09/2024, 07:00 AM, +0000 UTC",
            "iso_date": "2024-09-09T07:00:00Z",
        },
        {
            "title": "SEBI probe into Brightwell Polymers IPO funds",
            "link": "https://n.example/2",
            "date": "12/04/2024, 08:00 AM, +0000 UTC",
            "iso_date": "2024-12-04T08:00:00Z",
        },
        {"title": "Unrelated company news", "link": "https://n.example/3", "date": "Sep 1, 2024"},
    ]
}
VIDEOS: dict[str, JsonValue] = {
    "video_results": [
        {"title": "Brightwell Polymers IPO GMP today - apply?"},
        {"title": "Brightwell Polymers company profile"},
        {"title": "Other IPO GMP"},
    ]
}


class Routed(FakeSearch):
    def query(self, engine, params, parent=None):  # type: ignore[no-untyped-def]
        self.bodies = {"google_news": NEWS, "youtube": VIDEOS}
        return super().query(engine, params, parent)


def test_adverse_news_after_the_cutoff_is_ignored_in_point_in_time_mode() -> None:
    found = footprint("BRIGHTWELL POLYMERS LIMITED", Routed({}))
    before = {s.rule: s for s in footprint_signals(found, date(2024, 9, 12))}
    now = {s.rule: s for s in footprint_signals(found, None)}
    assert before["NW-01"].status is Status.CONSISTENT
    assert now["NW-01"].status is Status.INCONSISTENT
    assert banned_terms(now["NW-01"].text) == []


def test_promotion_volume_is_context_and_never_a_verdict() -> None:
    found = footprint("BRIGHTWELL POLYMERS LIMITED", Routed({}))
    volume = {s.rule: s for s in footprint_signals(found, None)}["HY-01"]
    assert volume.status is Status.NOT_APPLICABLE
    assert (found.videos, found.promo_videos) == (2, 1)
    assert "2 YouTube video(s) (1 about price" in volume.text
    assert "Context, not a verdict" in volume.text


def test_month_first_news_dates_never_leak_a_december_story_into_april() -> None:
    # the display date 12/04/2024 is 4 December; read day-first it would pass a September cutoff
    found = footprint("BRIGHTWELL POLYMERS LIMITED", Routed({}))
    adverse = [a for a in found.articles if a.adverse]
    assert [a.when for a in adverse] == [date(2024, 12, 4)]
    assert footprint_signals(found, date(2024, 9, 12))[0].status is Status.CONSISTENT


def test_a_place_type_given_as_a_list_is_joined() -> None:
    found = site_visit(
        ISSUER, FACTORY, FakeSearch({"google_maps": place(type=["Factory", "Manufacturer"])})
    )
    assert found.place_type == "Factory, Manufacturer"
