# facts printed on the cover: the prospectus date, used as the default point-in-time cutoff
import re
from collections import Counter
from datetime import date

from quaoar.domain.dates import parse_date
from quaoar.prospectus.acquire import IntakeError
from quaoar.prospectus.pdf import Page

COVER_PAGES = 3
FRONT_PAGES = 8
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
NUMERIC = r"\d{1,2}[./-]\d{1,2}[./-]\d{4}"
DATED = re.compile(
    rf"\bdated\s*:?\s*((?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})|(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH},?\s+\d{{4}})|(?:{NUMERIC}))",
    re.I,
)


def prospectus_date(pages: list[Page]) -> date | None:
    text = " ".join(p.text for p in pages[:COVER_PAGES])

    # lines wrap mid-date and some covers put a space before the comma
    flat = re.sub(r"\s+,", ",", " ".join(text.split()))
    found = [d for raw in DATED.findall(flat) if (d := parse_date(raw)) is not None]
    if not found:
        return None
    # the most repeated date on the cover wins; a tie goes to the later one
    counts = Counter(found)
    return max(counts, key=lambda d: (counts[d], d))


def require_prospectus(pages: list[Page]) -> None:
    # refuse a cv, a bill or a scan before any search is paid for
    front = " ".join(" ".join(p.text.split()) for p in pages[:FRONT_PAGES]).lower()
    if not front.strip():
        raise IntakeError("no_text", "the pdf has no readable text (a scan or images?)")
    if "prospectus" not in front or "equity shares" not in front:
        raise IntakeError(
            "not_a_prospectus",
            "this doesn't look like an IPO prospectus: the first pages don't say 'Prospectus' and 'Equity Shares'",
        )
