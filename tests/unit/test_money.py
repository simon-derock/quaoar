# spec: SPEC-MNY-01, SPEC-MNY-02, SPEC-MNY-03
import pytest
from hypothesis import given
from hypothesis import strategies as st

from quaoar.domain.money import MoneyParseError, format_inr, parse_inr

CRORE_PAISE = 10**7 * 100
LAKH_PAISE = 10**5 * 100


@pytest.mark.parametrize(
    ("text", "paise"),
    [
        ("Rs. 17.70 crore", 1770 * CRORE_PAISE // 100),
        ("INR 17.7 cr", 1770 * CRORE_PAISE // 100),
        ("Rs 1.5 Cr.", 150 * CRORE_PAISE // 100),
        ("₹1,77,00,000", 17_700_000 * 100),
        ("177.00 lakhs", 177 * LAKH_PAISE),
        ("₹ 0.50 lakh", 50_000 * 100),
        ("Rs. 20,000", 20_000 * 100),
        ("Rs.6,668", 6_668 * 100),
        ("12,500.75", 1_250_075),
        ("2.5 lacs", 250_000 * 100),
        ("3 million", 3_000_000 * 100),
        ("(₹ 12.34)", -1_234),
        ("-₹1,000.00", -100_000),
    ],
)
def test_parses_indian_amounts_to_paise(text: str, paise: int) -> None:
    assert parse_inr(text) == paise


def test_table_unit_header_scales_bare_numbers() -> None:
    assert parse_inr("45.00", unit="₹ in lakhs") == 45 * LAKH_PAISE
    assert parse_inr("1,770.00", unit="(Rs. in Crores)") == 1770 * CRORE_PAISE


def test_amount_written_with_its_own_unit_or_sign_ignores_the_header() -> None:
    assert parse_inr("Rs. 20,000", unit="₹ in lakhs") == 20_000 * 100
    assert parse_inr("2 crore", unit="₹ in lakhs") == 2 * CRORE_PAISE


def test_text_without_an_amount_is_an_error() -> None:
    with pytest.raises(MoneyParseError):
        parse_inr("not disclosed")


def test_result_is_an_int_never_a_float() -> None:
    assert type(parse_inr("Rs. 17.70 crore")) is int


def test_full_format_uses_indian_grouping() -> None:
    assert format_inr(1_770_000_000) == "₹1,77,00,000.00"
    assert format_inr(-100_000) == "-₹1,000.00"
    assert format_inr(5) == "₹0.05"


def test_short_format_uses_crore_and_lakh() -> None:
    assert format_inr(1770 * CRORE_PAISE // 100, style="short") == "₹17.70 Cr"
    assert format_inr(45 * LAKH_PAISE, style="short") == "₹45.00 L"
    assert format_inr(20_000 * 100, style="short") == "₹20,000.00"


@given(st.integers(min_value=-(10**14), max_value=10**14))
def test_full_format_round_trips_exactly(paise: int) -> None:
    assert parse_inr(format_inr(paise)) == paise


@pytest.mark.parametrize(
    "text",
    ["1" * 40, "1" * 100_000, "Rs. " + "9" * 35],
    ids=["40-digits", "100k-digits", "rs-35-digits"],
)
def test_digit_runs_longer_than_any_real_amount_are_rejected(text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_inr(text)


def test_a_match_never_starts_inside_a_longer_number() -> None:
    assert parse_inr("ref 12345678901234567890123456789012345 or Rs. 5") == 500
