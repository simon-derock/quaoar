# spec: SPEC-VX-08, SPEC-EVT-01, SPEC-RT-04
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from quaoar.domain.claims import QuoteClaim, Quotes
from quaoar.domain.findings import Status
from quaoar.events import Emitter, MemorySink
from quaoar.llm.client import LlmError
from quaoar.prospectus.acquire import from_path
from quaoar.prospectus.pdf import Page
from quaoar.scan import issuer_name, run_scan, scan_id_for
from tests.fakes import FixedClock
from tests.pdfgen import make_pdf
from tests.unit.checks.test_registry import INSTA, ZAUBA
from tests.unit.checks.test_vendor import FakeSearch, maps_body, registry_body
from tests.unit.prospectus.test_extract import FakeSource

PAGES = [
    ["DRAFT PROSPECTUS", "DEMO SOFTWARE LIMITED", "Public issue of Equity Shares", "Our Company was incorporated in 2015"],
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


def test_one_vendor_quoted_for_several_items_gets_one_check_using_its_largest_quote(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(make_pdf(PAGES))
    sink = MemorySink()
    clock = FixedClock()
    search = FakeSearch({"duckduckgo": registry_body(ZAUBA, INSTA), "google_maps": maps_body()})
    quotes = Quotes(
        items=[QUOTE, QUOTE.model_copy(update={"item": "second item", "amount_text": "500.00"})]
    )
    result = run_scan(
        from_path(pdf),
        search=search,
        claims=FakeSource({"quotes": quotes}),
        emit=Emitter("d", sink, clock),
        clock=clock,
        cutoff=date(2024, 9, 3),
    )
    vendor_stages = [e for e in sink.events if e.type == "stage" and e.data.get("name") == "vendor"]
    assert len(vendor_stages) == 1
    assert [s.rule for s in result.signals if s.rule == "VX-03"] == ["VX-03"]
    assert "1,770 times" in next(s.text for s in result.signals if s.rule == "VX-03")


def test_the_issuer_is_the_name_repeated_on_the_cover_not_the_first_company_listed() -> None:
    cover = Page(
        1,
        "BOOK RUNNING LEAD MANAGER\nSWASTIKA INVESTMART LIMITED\nREGISTRAR TO THE ISSUE\nMAASHITLA SECURITIES PRIVATE LIMITED\n",
        needs_ocr=False,
    )
    second = Page(
        2,
        "TBI CORN LIMITED\nINITIAL PUBLIC ISSUE OF UPTO 47,80,800 EQUITY SHARES OF TBI CORN LIMITED\nOUR COMPANY, TBI CORN LIMITED, IS",
        needs_ocr=False,
    )
    assert issuer_name([cover, second]) == "TBI CORN LIMITED"


def test_a_prospectus_whose_sections_cant_be_located_says_so_on_the_card(tmp_path: Path) -> None:
    # no contents list: nothing can be located, so only news is checked, and the card must not look complete
    pdf = tmp_path / "flat.pdf"
    pdf.write_bytes(make_pdf([PAGES[0], ["1 | P a g e", "Some body text about the company."]]))
    clock = FixedClock()
    result = run_scan(
        from_path(pdf),
        search=FakeSearch({}),
        claims=FakeSource({}),
        emit=Emitter("flat", MemorySink(), clock),
        clock=clock,
        cutoff=date(2024, 9, 3),
    )
    notes = [c.text for c in result.card.context]
    assert any("couldn't locate" in note for note in notes)
    assert all("fraud" not in note.lower() for note in notes)


def test_a_cover_that_prints_the_name_in_mixed_case_still_names_the_issuer() -> None:
    cover = Page(
        1,
        "Red Herring Prospectus\nMV Electrosystems Limited\nCorporate Identity Number: U31401HR2009PLC140536\n",
        needs_ocr=False,
    )
    third = Page(
        3,
        "Red Herring Prospectus\nMV Electrosystems Limited\nKFin Technologies Limited\n",
        needs_ocr=False,
    )
    assert issuer_name([cover, third]) == "MV Electrosystems Limited"


def test_a_bare_legal_suffix_line_is_not_taken_for_the_issuer() -> None:
    cover = Page(1, "Red Herring Prospectus\nPrivate Limited\nPrivate Limited\n", needs_ocr=False)
    assert issuer_name([cover]) == "Unnamed issuer"


def test_the_issuer_is_counted_across_cases_so_a_registrar_named_twice_in_capitals_does_not_win() -> (
    None
):
    first = Page(
        1,
        "Red Herring Prospectus\nDesco Infratech Limited\nREGISTRAR TO THE ISSUE\nBIGSHARE SERVICES PRIVATE LIMITED\n",
        needs_ocr=False,
    )
    third = Page(
        3,
        "DESCO INFRATECH LIMITED\nSHARES OF DESCO INFRATECH LIMITED (OUR COMPANY)\nBIGSHARE SERVICES PRIVATE LIMITED\n",
        needs_ocr=False,
    )
    assert issuer_name([first, third]) == "DESCO INFRATECH LIMITED"


def test_the_second_half_of_a_wrapped_registrar_name_is_not_taken_for_the_issuer() -> None:
    cover = Page(
        1,
        "BEELINE CAPITAL ADVISORS\nPRIVATE LIMITED\nKFIN TECHNOLOGIES\nPRIVATE LIMITED\nLINK INTIME\nPRIVATE LIMITED\n"
        "MEHUL TELECOM LIMITED\n",
        needs_ocr=False,
    )
    third = Page(3, "MEHUL TELECOM LIMITED\n", needs_ocr=False)
    assert issuer_name([cover, third]) == "MEHUL TELECOM LIMITED"


class DownSource:
    # a model that is unavailable for every request, as when a key's monthly quota is spent
    def extract[T: BaseModel](
        self, task: str, output: type[T], text: str, parent: str | None = None
    ) -> T:
        raise LlmError(f"{task}: every Cohere key is rate limited or failing")


def test_a_card_whose_claims_could_not_be_read_says_it_is_incomplete(tmp_path: Path) -> None:
    pdf = tmp_path / "demo.pdf"
    pdf.write_bytes(make_pdf(PAGES))
    clock = FixedClock()
    result = run_scan(
        from_path(pdf),
        search=FakeSearch({}),
        claims=DownSource(),
        emit=Emitter("down", MemorySink(), clock),
        clock=clock,
        cutoff=date(2024, 9, 3),
    )
    notes = [c.text for c in result.card.context]
    assert any("couldn't read" in note and "incomplete" in note for note in notes)
    assert all("fraud" not in note.lower() for note in notes)
