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
        ("OUTSTANDING LITIGATION AND MATERIAL DEVLOPMENTS", "litigation"),
        ("GROUP ENTITIES OF OUR COMPANY", "group_companies"),
        ("SECTION - V - GENERAL INFORMATION", "general_information"),
        ("SECTION - XII - OTHER REGULATORY AND STATUTORY DISCLOSURES", "regulatory"),
        ("OTHER REGULATORY AND STATUTORY DISCLOSURE", "regulatory"),
        ("SECTION VII - PARTICULARS OF THE ISSUE", None),
        ("OUR MANAGEMENT", None),
    ],
)
def test_title_variants_seen_in_real_prospectuses_map_to_the_same_section(
    title: str, name: str | None
) -> None:
    assert target_name(title) == name


def test_a_contents_list_without_dotted_leaders_is_read() -> None:
    # "TITLE 81": the page number follows the title after a space, as in some SME prospectuses
    toc = [
        "TABLE OF CONTENTS",
        "SECTION CONTENTS PAGE NO.",
        "I. GENERAL",
        "GENERAL INFORMATION 81",
        "OBJECTS OF THE OFFER 112",
        "OUR BUSINESS 164",
    ]
    pages = [
        Page(1, "cover page with enough text to not be empty", needs_ocr=False),
        Page(2, "\n".join(toc), needs_ocr=False),
        page(3, "GENERAL INFORMATION"),
        page(4, "OBJECTS OF THE OFFER"),
        page(5, "OUR BUSINESS"),
    ]
    found = locate_sections(pages)
    assert set(found.sections) == {"general_information", "objects", "business"}


def test_a_list_headed_index_with_page_headers_that_say_page_n_of_m_is_read() -> None:
    toc = [
        "INDEX",
        "SECTION III- INTRODUCTION..........................57",
        "GENERAL INFORMATION..........................82",
        "OBJECTS OF THE ISSUE.........................97",
    ]

    def numbered(number: int, *lines: str) -> Page:
        text = "\n".join([f"Page {number - 2} of 346", *lines, "body text " * 8])
        return Page(number, text, needs_ocr=False)

    pages = [
        Page(1, "cover page with enough text to not be empty", needs_ocr=False),
        Page(2, "\n".join(toc), needs_ocr=False),
        numbered(3, "SECTION III- INTRODUCTION", "x", "y", "z"),
        numbered(4, "GENERAL INFORMATION"),
        numbered(5, "OBJECTS OF THE ISSUE"),
    ]
    found = locate_sections(pages)
    assert {n: (s.start, s.end) for n, s in found.sections.items()} == {
        "general_information": (4, 4),
        "objects": (5, 5),
    }


def test_body_text_ending_in_a_number_is_not_mistaken_for_a_contents_line() -> None:
    toc = ["CONTENTS", "The company has 12 offices and sells 40", "GENERAL INFORMATION 81"]
    pages = [Page(2, "\n".join(toc), needs_ocr=False), page(3, "GENERAL INFORMATION")]
    assert set(locate_sections(pages).sections) == {"general_information"}


def test_ampersand_and_plural_wording_differences_between_contents_and_heading_are_bridged() -> (
    None
):
    toc = [
        "TABLE OF CONTENTS",
        "OUR PROMOTERS & PROMOTER GROUP 4",
        "OUTSTANDING LITIGATIONS AND OTHER MATERIAL DEVELOPMENTS 5",
    ]
    pages = [
        Page(1, "\n".join(toc), needs_ocr=False),
        page(3, "OUR PROMOTERS AND PROMOTER GROUP"),
        page(4, "OUTSTANDING LITIGATION AND MATERIAL DEVELOPMENTS"),
    ]
    found = locate_sections(pages)
    assert set(found.sections) == {"promoters", "litigation"}


def contents_then(toc: list[str], *rest: Page) -> list[Page]:
    return [Page(1, "\n".join(toc), needs_ocr=False), *rest]


@pytest.mark.parametrize("heading", ["TABLE OF CONTENT", "TABLE CONTENTS", "CONTENT"])
def test_contents_headings_without_the_final_s_or_the_of_are_read(heading: str) -> None:
    pages = contents_then(
        [heading, "GENERAL INFORMATION..........58"], page(3, "GENERAL INFORMATION")
    )
    assert set(locate_sections(pages).sections) == {"general_information"}


def test_contents_lines_with_underscore_leaders_are_read() -> None:
    toc = [
        "TABLE OF CONTENTS",
        "SECTION IV - GENERAL INFORMATION ________________58",
        "OBJECTS OF THE OFFER ____89",
    ]
    pages = contents_then(
        toc, page(3, "SECTION IV - GENERAL INFORMATION"), page(4, "OBJECTS OF THE OFFER")
    )
    assert set(locate_sections(pages).sections) == {"general_information", "objects"}


def test_a_stray_punctuation_line_cannot_pose_as_a_title_and_skip_later_sections() -> None:
    # a contents entry that normalises to nothing must not match a lone "." at the top of a later page
    toc = [
        "CONTENTS",
        "OUR BUSINESS ....... 3",
        ". ....... 4",
        "OUTSTANDING LITIGATION AND MATERIAL DEVELOPMENTS ....... 5",
    ]
    pages = contents_then(
        toc,
        page(2, "OUR BUSINESS"),
        page(3, "filler"),
        page(4, "OUTSTANDING LITIGATION AND MATERIAL DEVELOPMENTS"),
        Page(5, ".\nbody text body text body text body text", needs_ocr=False),
    )
    assert set(locate_sections(pages).sections) == {"business", "litigation"}
