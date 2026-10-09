# spec: SPEC-PDF-04
from datetime import date

import pytest

from quaoar.prospectus.acquire import IntakeError
from quaoar.prospectus.meta import prospectus_date, require_prospectus
from quaoar.prospectus.pdf import Page


def pages(*texts: str) -> list[Page]:
    return [Page(i, t, needs_ocr=False) for i, t in enumerate(texts, start=1)]


def test_a_date_split_across_lines_with_an_ordinal_is_read() -> None:
    assert prospectus_date(pages("Dated: June 05th\n, 2024\nPlease read section 26")) == date(
        2024, 6, 5
    )


def test_the_most_repeated_cover_date_wins() -> None:
    cover = "Dated: July 18, 2024 ... Dated: June 28, 2024 ... Dated: July 18, 2024"
    assert prospectus_date(pages(cover)) == date(2024, 7, 18)


def test_day_first_dates_and_no_date() -> None:
    assert prospectus_date(pages("Dated 17th May, 2024")) == date(2024, 5, 17)
    assert prospectus_date(pages("a cover with no date at all")) is None


def test_dates_beyond_the_cover_pages_are_ignored() -> None:
    assert prospectus_date(pages("x", "y", "z", "Dated: June 05, 2024")) is None


def test_a_prospectus_cover_is_accepted() -> None:
    require_prospectus(
        pages("DRAFT RED HERRING PROSPECTUS\nPublic issue of 24,00,000 Equity Shares of Rs 10 each")
    )


@pytest.mark.parametrize(
    ("texts", "rule"),
    [
        (["Resume of A. Kumar. Skills: Python. Experience: 3 years."], "not_a_prospectus"),
        (
            ["Electricity bill March 2026. Equity shares are not mentioned here."],
            "not_a_prospectus",
        ),
        (["Prospectus of a mutual fund scheme. Units, not shares."], "not_a_prospectus"),
        ([], "no_text"),
        (["", "  "], "no_text"),
    ],
)
def test_other_documents_are_refused_before_any_search(texts: list[str], rule: str) -> None:
    with pytest.raises(IntakeError) as caught:
        require_prospectus(pages(*texts))
    assert caught.value.rule == rule


@pytest.mark.parametrize(
    ("cover", "expected"),
    [
        ("Red Herring Prospectus Dated: 07.10.2026 Please read Section 26", date(2026, 10, 7)),
        ("Dated 7/10/2026", date(2026, 10, 7)),
        ("Dated: 07-10-2026", date(2026, 10, 7)),
        ("Dated: 7th October, 2026", date(2026, 10, 7)),
    ],
)
def test_a_numeric_cover_date_is_read_day_first(cover: str, expected: date) -> None:
    assert prospectus_date(pages(cover)) == expected


def test_a_numeric_date_not_after_dated_is_not_taken_for_the_cover_date() -> None:
    assert prospectus_date(pages("CIN registered 12.05.2019 and a phone 07.10.2026")) is None
