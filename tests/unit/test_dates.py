# spec: SPEC-DOM-03
from datetime import UTC, date, datetime

import pytest

from quaoar.domain.dates import parse_date

SEARCHED_AT = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2024-03-12", date(2024, 3, 12)),
        ("12th March, 2024", date(2024, 3, 12)),
        ("12 March 2024", date(2024, 3, 12)),
        ("1st Sept 2025", date(2025, 9, 1)),
        ("12-Mar-2024", date(2024, 3, 12)),
        ("March 12, 2024", date(2024, 3, 12)),
        ("Dec 3, 2024", date(2024, 12, 3)),
        ("12.03.2024", date(2024, 3, 12)),
        ("03/12/2024", date(2024, 12, 3)),
        ("Order dated December 03, 2024 in the matter of", date(2024, 12, 3)),
    ],
)
def test_parses_absolute_dates_in_indian_order(text: str, expected: date) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3 days ago", date(2026, 10, 6)),
        ("an hour ago", date(2026, 10, 9)),
        ("1 week ago", date(2026, 10, 2)),
        ("1 month ago", date(2026, 9, 9)),
        ("2 years ago", date(2024, 10, 9)),
        ("yesterday", date(2026, 10, 8)),
    ],
)
def test_relative_dates_resolve_against_the_search_time(text: str, expected: date) -> None:
    assert parse_date(text, ref=SEARCHED_AT) == expected


def test_relative_date_without_a_reference_is_unknown() -> None:
    assert parse_date("3 days ago") is None


def test_month_end_clamps_when_going_back_months() -> None:
    ref = datetime(2026, 3, 31, tzinfo=UTC)
    assert parse_date("1 month ago", ref=ref) == date(2026, 2, 28)


@pytest.mark.parametrize("text", ["31.02.2024", "no date here", "March 2024", ""])
def test_impossible_or_partial_dates_are_unknown(text: str) -> None:
    assert parse_date(text) is None
