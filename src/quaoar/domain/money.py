# indian rupee amounts as integer paise; Decimal inside, never float
import re
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

PAISE_PER_RUPEE = 100
CRORE_PAISE = 10**7 * PAISE_PER_RUPEE
LAKH_PAISE = 10**5 * PAISE_PER_RUPEE

# longer spellings sit first so "crores" wins over "cr"
UNIT_WORDS = r"crores?|crs?|lakhs?|lacs?|lac|millions?|mn|thousands?"
UNIT_SCALE = {"cr": 10**7, "la": 10**5, "mi": 10**6, "mn": 10**6, "th": 10**3}

# whitespace is only allowed after a currency sign: two optional \s* runs in a row
# backtrack cubically on long blank stretches
# a match never starts or ends inside a longer digit run, so a 40-digit reference
# number is not half-read as an amount
AMOUNT = re.compile(
    r"(?<![\d.,])(?P<open>\()?(?P<minus>-)?(?:(?P<cur>₹|rs\.?|inr)\s{0,3})?"
    r"(?P<num>\d[\d,]{0,30}(?:\.\d{1,12})?)(?!\d)\s{0,3}"
    rf"(?P<unit>{UNIT_WORDS})?(?![a-z])",
    re.IGNORECASE,
)
# 31 integer digits, 12 decimals and a 10^9 scale all fit exactly in 64 digits
DECIMAL_DIGITS = 64
UNIT_ONLY = re.compile(rf"\b(?P<unit>{UNIT_WORDS})\b", re.IGNORECASE)


class MoneyParseError(ValueError):
    pass


# --- public ---


def parse_inr(text: str, unit: str | None = None) -> int:
    match = pick_amount(text)

    # an amount written out with its own unit or a ₹ sign ignores the table header
    own_unit = match.group("unit")
    if own_unit:
        scale = unit_scale(own_unit)
    elif match.group("cur"):
        scale = 1
    else:
        scale = header_scale(unit)

    with localcontext(prec=DECIMAL_DIGITS):
        rupees = Decimal(match.group("num").replace(",", "")) * scale
        paise = int((rupees * PAISE_PER_RUPEE).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    negative = bool(match.group("open") or match.group("minus"))
    return -paise if negative else paise


def format_inr(paise: int, style: Literal["full", "short"] = "full") -> str:
    sign = "-" if paise < 0 else ""
    size = abs(paise)

    # short form reads like a headline; full form round-trips exactly
    if style == "short" and size >= CRORE_PAISE:
        return f"{sign}₹{two_places(size, CRORE_PAISE)} Cr"
    if style == "short" and size >= LAKH_PAISE:
        return f"{sign}₹{two_places(size, LAKH_PAISE)} L"

    rupees, rest = divmod(size, PAISE_PER_RUPEE)
    return f"{sign}₹{indian_grouping(rupees)}.{rest:02d}"


# --- helpers ---


def pick_amount(text: str) -> re.Match[str]:
    matches = list(AMOUNT.finditer(text))
    if not matches:
        raise MoneyParseError(f"no amount in {text[:60]!r}")

    # years and serial numbers look like amounts too, so prefer a match carrying ₹ or a unit
    marked = [m for m in matches if m.group("cur") or m.group("unit")]
    return marked[0] if marked else matches[0]


def unit_scale(word: str) -> int:
    word = word.lower()
    key = "mn" if word == "mn" else word[:2]
    return UNIT_SCALE[key]


def header_scale(header: str | None) -> int:
    if header is None:
        return 1
    found = UNIT_ONLY.search(header)
    return unit_scale(found.group("unit")) if found else 1


def two_places(paise: int, per_unit: int) -> Decimal:
    return (Decimal(paise) / per_unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def indian_grouping(rupees: int) -> str:
    digits = str(rupees)
    if len(digits) <= 3:
        return digits

    # last three digits stay together, everything before groups in pairs
    head, tail = digits[:-3], digits[-3:]
    pairs: list[str] = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head, *pairs, tail])
