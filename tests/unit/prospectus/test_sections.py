# spec: SPEC-SEC-01, SPEC-SEC-02
from pathlib import Path

import pytest

from quaoar.prospectus.pdf import Page, read_pages
from quaoar.prospectus.sections import locate_sections, target_name

TOC = [
    "Table of Contents",
    "SECTION I \u2013 GENERAL..........................",
    "GENERAL INFORMATION..........................",
    "SECTION V \u2013 PARTICULARS OF THE ISSUE..........",
    "OBJECTS OF THE ISSUE.........................",
    "BASIS FOR ISSUE PRICE .......................",
    "BUSINESS OVERVIEW ...........................",
    "OUR PROMOTERS AND PROMOTER GROUP ............",
    "MANAGEMENT\u2019S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF",
    "OPERATIONS...................................",
    "OUTSTANDING LITIGATIONS AND MATERIAL DEVELOPEMENT ...",
    "OTHER REGULATORY AND STATUTORY DISCLOSURES ...",
    "DECLARATION .................................",
]


def page(number: int, *lines: str) -> Page:
    text = "\n".join([f"{number - 2} | P a g e", *lines, "body text " * 8])
    return Page(number, text, needs_ocr=False)


def document() -> list[Page]:
    return [
        Page(1, "cover page with enough text to not be empty", needs_ocr=False),
        Page(2, "\n".join(TOC), needs_ocr=False),
        page(3, "SECTION I \u2013 GENERAL"),
        # the summary repeats headings mid-page; order and top-of-page keep it out
        page(
            4, "SECTION II - SUMMARY", "some text", "more text", "even more", "OBJECTS OF THE ISSUE"
        ),
        page(5, "GENERAL INFORMATION"),
        page(6, "SECTION V \u2013 PARTICULARS OF THE ISSUE", "OBJECTS OF THE ISSUE"),
        page(7, "continued objects"),
        page(8, "BASIS FOR ISSUE PRICE"),
        page(9, "BUSINESS OVERVIEW"),
        page(10, "OUR PROMOTERS AND PROMOTER GROUP"),
        page(
            11,
            "MANAGEMENT\u2019S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS",
        ),
        page(12, "OUTSTANDING LITIGATIONS AND MATERIAL DEVELOPEMENT"),
        page(13, "OTHER REGULATORY AND STATUTORY DISCLOSURES"),
        page(14, "DECLARATION"),
    ]


def test_sections_start_at_their_heading_and_end_before_the_next_title() -> None:
    found = locate_sections(document())
    spans = {name: (s.start, s.end) for name, s in found.sections.items()}
    assert spans == {
        "general_information": (5, 5),
        "objects": (6, 7),
        "business": (9, 9),
        "promoters": (10, 10),
        "litigation": (12, 12),
        "regulatory": (13, 13),
    }
    assert found.toc_page == 2


def test_sections_not_in_the_document_are_reported_missing_not_guessed() -> None:
    assert locate_sections(document()).missing == ("group_companies",)


def test_heading_that_never_appears_at_a_page_top_is_missing() -> None:
    pages = [p for p in document() if p.number != 13]
    assert "regulatory" in locate_sections(pages).missing


def test_without_a_table_of_contents_nothing_is_guessed() -> None:
    pages = [p for p in document() if p.number != 2]
    found = locate_sections(pages)
    assert found.sections == {}
    assert found.toc_page is None


TRAFIKSOL = (
    next(Path("cases/pdfs").glob("c9153f93*.pdf"), None) if Path("cases/pdfs").is_dir() else None
)


@pytest.mark.skipif(TRAFIKSOL is None, reason="real prospectus is local only, never committed")
def test_real_trafiksol_prospectus_sections() -> None:
    assert TRAFIKSOL is not None
    found = locate_sections(read_pages(TRAFIKSOL))
    starts = {name: s.start for name, s in found.sections.items()}
    assert starts["objects"] == 87
    assert starts["business"] == 123
    assert starts["litigation"] == 270
    assert starts["regulatory"] == 282
    assert found.missing == ()


@pytest.mark.parametrize(
    ("title", "name"),
    [
        ("SECTION V - GENERAL INFORMATION", "general_information"),
        ("OUR PROMOTERS AND PROMOTERS GROUP", "promoters"),
        ("OUR PROMOTER AND PROMOTER GROUP", "promoters"),
        ("SECTION XI - INFORMATION WITH RESPECT TO GROUP COMPANIES/ ENTITIES", "group_companies"),
        ("OUR GROUP COMPANY", "group_companies"),
        ("SECTION XII - OTHER REGULATORY AND STATUTORY DISCLOSURES", "regulatory"),
        ("OUTSTANDING LITIGATIONS AND MATERIAL DEVELOPMENTS", "litigation"),
        ("SECTION VII - PARTICULARS OF THE ISSUE", None),
        ("OUR MANAGEMENT", None),
    ],
)
def test_title_variants_seen_in_real_prospectuses_map_to_the_same_section(
    title: str, name: str | None
) -> None:
    assert target_name(title) == name
