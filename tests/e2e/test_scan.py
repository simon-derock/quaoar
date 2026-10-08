# spec: SPEC-VX-08, SPEC-EVT-01, SPEC-RT-04
from datetime import date
from pathlib import Path

from quaoar.domain.claims import QuoteClaim, Quotes
from quaoar.domain.findings import Status
from quaoar.events import Emitter, MemorySink
from quaoar.prospectus.acquire import from_path
from quaoar.prospectus.pdf import Page
from quaoar.scan import issuer_name, run_scan, scan_id_for
from tests.fakes import FixedClock
from tests.pdfgen import make_pdf
from tests.unit.checks.test_registry import INSTA, ZAUBA
from tests.unit.checks.test_vendor import FakeSearch, maps_body, registry_body
from tests.unit.prospectus.test_extract import FakeSource

PAGES = [
    ["DRAFT PROSPECTUS", "DEMO SOFTWARE LIMITED", "Our Company was incorporated in 2015"],
    ["Table of Contents", "OBJECTS OF THE ISSUE ............ 3", "DECLARATION ............ 4"],
    ["3 | P a g e", "OBJECTS OF THE ISSUE", "Quotation from: - OASIS CORPCARE PRIVATE LIMITED",
     "Amount (In Lakhs) 1,770.00 Quotation Date: - May 16, 2024"],
    ["4 | P a g e", "DECLARATION", "We declare that all statements are true."],
]  # fmt: skip
QUOTE = QuoteClaim(
    page=3,
    vendor="OASIS CORPCARE PRIVATE LIMITED",
    item="",
    amount_text="1,770.00",
    unit_text="Lakhs",
    quote_date_text="May 16, 2024",
)


def run(tmp_path: Path) -> tuple[object, MemorySink]:
    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(make_pdf(PAGES))
    sink = MemorySink()
    clock = FixedClock()
    emit = Emitter("demo", sink, clock)
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": maps_body()})
    result = run_scan(
        from_path(pdf),
        search=search,
        claims=FakeSource({"quotes": Quotes(items=[QUOTE])}),
        emit=emit,
        clock=clock,
        cutoff=date(2024, 9, 3),
    )
    return result, sink


def test_scan_end_to_end_flags_the_vendor_from_the_pdf(tmp_path: Path) -> None:
    result, _ = run(tmp_path)
    card = result.card  # type: ignore[attr-defined]
    assert card.company == "DEMO SOFTWARE LIMITED"
    assert card.inconsistent == 1
    assert card.top[0].rule == "VX-03"
    assert card.top[0].status is Status.INCONSISTENT


def test_every_event_chains_back_to_the_intake_stage(tmp_path: Path) -> None:
    _, sink = run(tmp_path)
    by_id = {e.id: e for e in sink.events}
    root = sink.events[0]
    assert root.data["name"] == "intake"
    for event in sink.events[1:]:
        current = event
        while current.parent is not None:
            current = by_id[current.parent]
        assert current.id == root.id


def test_scan_id_is_stable_for_the_same_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(make_pdf(PAGES))
    assert scan_id_for(from_path(pdf)) == scan_id_for(from_path(pdf))


def test_issuer_name_falls_back_when_the_cover_has_none() -> None:
    assert issuer_name([Page(1, "nothing in capitals here", needs_ocr=False)]) == "Unnamed issuer"


def test_scan_adds_banker_signals_when_a_lead_manager_is_found(tmp_path: Path) -> None:
    from quaoar.domain.claims import LeadManagerClaim, LeadManagers

    pages = [
        PAGES[0],
        ["Table of Contents", "GENERAL INFORMATION ............ 3", "OBJECTS OF THE ISSUE ............ 4", "DECLARATION ............ 5"],
        ["3 | P a g e", "GENERAL INFORMATION", "Book Running Lead Manager", "FIRST DEMO CAPITAL PRIVATE LIMITED"],
        PAGES[2],
        PAGES[3],
    ]  # fmt: skip
    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(make_pdf(pages))
    clock = FixedClock()
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": maps_body()})
    managers = LeadManagers(
        items=[LeadManagerClaim(page=3, name="FIRST DEMO CAPITAL PRIVATE LIMITED")]
    )
    answers = {
        "quotes": Quotes(items=[QUOTE.model_copy(update={"page": 4})]),
        "lead_managers": managers,
    }
    result = run_scan(
        from_path(pdf),
        search=search,
        claims=FakeSource(answers),
        emit=Emitter("d", MemorySink(), clock),
        clock=clock,
    )
    assert {"BK-04", "BK-05"} <= {s.rule for s in result.signals}
