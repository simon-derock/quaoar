# dates as printed in prospectuses, orders and search results, read in indian day-month order
import calendar
import re
from datetime import date, datetime, timedelta

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
MONTH = r"(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
ORDINAL = r"(?:st|nd|rd|th)?"

ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
DAY_FIRST = re.compile(rf"\b(?P<d>\d{{1,2}}){ORDINAL}[\s-]+{MONTH}[\s,.-]+(?P<y>\d{{4}})\b", re.I)
MONTH_FIRST = re.compile(rf"\b{MONTH}\s+(?P<d>\d{{1,2}}){ORDINAL},?\s+(?P<y>\d{{4}})\b", re.I)
NUMERIC = re.compile(r"\b(?P<d>\d{1,2})[./-](?P<m>\d{1,2})[./-](?P<y>\d{4})\b")
RELATIVE = re.compile(
    r"\b(?P<n>\d+|an?)\s+(?P<unit>minute|hour|day|week|month|year)s?\s+ago\b", re.I
)
YESTERDAY = re.compile(r"\byesterday\b", re.I)


def parse_date(text: str, *, ref: datetime | None = None) -> date | None:
    found = absolute_date(text)
    if found is not None or ref is None:
        return found
    return relative_date(text, ref.date())


def absolute_date(text: str) -> date | None:
    # most explicit form first, so a stray number never wins over a written month
    for pattern in (ISO, DAY_FIRST, MONTH_FIRST, NUMERIC):
        match = pattern.search(text)
        if match:
            return safe_date(match)
    return None


def relative_date(text: str, today: date) -> date | None:
    if YESTERDAY.search(text):
        return today - timedelta(days=1)
    match = RELATIVE.search(text)
    if not match:
        return None

    count = 1 if match.group("n").lower() in {"a", "an"} else int(match.group("n"))
    unit = match.group("unit").lower()
    if unit in {"minute", "hour"}:
        return today
    if unit in {"day", "week"}:
        return today - timedelta(days=count * (7 if unit == "week" else 1))
    return minus_months(today, count * (12 if unit == "year" else 1))


def safe_date(match: re.Match[str]) -> date | None:
    groups = match.groupdict()
    month = MONTHS[groups["mon"][:3].lower()] if groups.get("mon") else int(groups["m"])
    try:
        return date(int(groups["y"]), month, int(groups["d"]))
    except ValueError:
        # 31.02.2024 is a typo in the source, not a date we should guess at
        return None


def minus_months(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 - months
    year, month_index = divmod(total, 12)
    last_day = calendar.monthrange(year, month_index + 1)[1]
    return date(year, month_index + 1, min(day.day, last_day))
