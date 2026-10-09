# facts printed on the cover: the prospectus date, used as the default point-in-time cutoff
import re
from collections import Counter
from datetime import date

from quaoar.domain.dates import parse_date
from quaoar.prospectus.pdf import Page

COVER_PAGES = 3
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATED = re.compile(
    rf"\bdated\s*:?\s*((?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})|(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH},?\s+\d{{4}}))",
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
