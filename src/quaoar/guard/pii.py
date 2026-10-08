# G5 PII mask: personal identifiers never leave the process, company facts stay
import re

from quaoar.guard.hits import Cleaned, GuardHit

PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR = re.compile(r"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)")
MOBILE = re.compile(r"(?<![\d+])(?:\+91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?!\d)")
FREE_MAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]{1,64}@(?:gmail|yahoo|hotmail|outlook|rediffmail|ymail|icloud|protonmail|proton)"
    r"\.(?:com|in|co\.in|me)\b",
    re.I,
)
# a number token must contain a digit, so "plot of land" is left alone;
# every quantifier is bounded so a long blank run cannot backtrack
HOUSE_NO = re.compile(
    r"\b(?:flat|house|h\.?\s?no\.?|plot|door)(?:\s{0,3}no\.?)?\s{0,3}[:#]?\s{0,3}"
    r"[\w/-]{0,20}\d[\w/-]{0,20}",
    re.I,
)

VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)  # fmt: skip
VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)  # fmt: skip
VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def mask_pii(text: str) -> Cleaned:
    hits = []

    # aadhaar first: its 12 digits would otherwise be half-eaten by the mobile pattern
    masked = AADHAAR.sub(aadhaar_or_keep, text)
    n = masked.count("[aadhaar]") - text.count("[aadhaar]")
    text = masked
    if n:
        hits.append(GuardHit("G5", "aadhaar", n))

    for rule, pattern, mask in (
        ("pan", PAN, "[pan]"),
        ("phone", MOBILE, "[phone]"),
        ("email", FREE_MAIL, "[email]"),
        ("house_no", HOUSE_NO, "[house no.]"),
    ):
        text, n = pattern.subn(mask, text)
        if n:
            hits.append(GuardHit("G5", rule, n))
    return Cleaned(text, tuple(hits))


def aadhaar_or_keep(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "[aadhaar]" if verhoeff_valid(digits) else match.group(0)


def verhoeff_valid(number: str) -> bool:
    check = 0
    for i, ch in enumerate(reversed(number)):
        check = VERHOEFF_D[check][VERHOEFF_P[i % 8][int(ch)]]
    return check == 0


def verhoeff_check_digit(number: str) -> str:
    check = 0
    for i, ch in enumerate(reversed(number)):
        check = VERHOEFF_D[check][VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return str(VERHOEFF_INV[check])
