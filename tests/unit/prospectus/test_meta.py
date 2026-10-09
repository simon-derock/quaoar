# spec: SPEC-PDF-04
from datetime import date

from quaoar.prospectus.meta import prospectus_date
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
