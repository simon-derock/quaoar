# company-registry facts read from search snippets (instafinancials, zaubacorp, tofler)
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit

from quaoar.domain.dates import parse_date
from quaoar.domain.money import MoneyParseError, parse_inr
from quaoar.domain.names import normalize_company, similarity

REGISTRY_DOMAINS = ("zaubacorp.com", "instafinancials.com", "tofler.in")
REGISTRY_QUERY = "(site:zaubacorp.com OR site:instafinancials.com OR site:tofler.in)"
NAME_MATCH = 0.85
LEGAL_SUFFIX = re.compile(r"\b(private|pvt\.?|limited|ltd\.?|llp)\b\.?", re.I)

CIN = re.compile(r"\b([UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b")
DATE = r"(\d{1,2}(?:st|nd|rd|th)?[\s-]+[A-Za-z]{3,9},?[\s-]+\d{4})"
INCORPORATED = re.compile(rf"incorporated on {DATE}", re.I)
STATUS = re.compile(
    r"\b(?:status (?:of the company )?is|status:)\s*"
    r"(active|strike off|struck off|under process of striking off|dormant|amalgamated|dissolved|"
    r"liquidated|under liquidation)\b",
    re.I,
)
MONEY = r"((?:₹|rs\.?|inr)\s?[\d,]{1,20}(?:\.\d{1,2})?)"
AUTHORISED = re.compile(rf"authori[sz]ed (?:share )?capital (?:is|of)\s*{MONEY}", re.I)
PAID_UP = re.compile(rf"paid[\s-]?up capital (?:is|of)\s*{MONEY}", re.I)
BUSINESS = re.compile(r"main line of business is ([^.]{3,80})\.", re.I)
AGM = re.compile(
    rf"(?:annual general meeting|\bagm\b)[^.]{{0,40}}?(?:on|was held on)\s+{DATE}", re.I
)
CITY = re.compile(r"(?:registered office|located) in ([A-Z][A-Za-z ]{2,30}),", re.I)
BALANCE_SHEET = re.compile(rf"balance sheet[^.]{{0,40}}?(?:on|dated|as on)\s+{DATE}", re.I)


FIELDS = (
    "cin", "incorporated", "status", "authorised_paise", "paid_up_paise",
    "business_line", "last_agm", "last_balance_sheet", "city",
)  # fmt: skip


@dataclass(slots=True)
class RegistryFacts:
    matched_urls: list[str] = field(default_factory=list)
    cin: str | None = None
    incorporated: date | None = None
    status: str | None = None
    authorised_paise: int | None = None
    paid_up_paise: int | None = None
    business_line: str | None = None
    last_agm: date | None = None
    last_balance_sheet: date | None = None
    city: str | None = None
    # which page stated each fact, so "show proof" opens the right snippet
    sources: dict[str, str] = field(default_factory=dict)


def registry_core(name: str) -> str:
    # the quoted query uses the distinctive words, legal forms dropped
    return " ".join(LEGAL_SUFFIX.sub(" ", name).split())


def is_registry_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in REGISTRY_DOMAINS)


def read_facts(company: str, results: Sequence[Mapping[str, object]]) -> RegistryFacts:
    facts = RegistryFacts()
    for result in results:
        url, title = str(result.get("link", "")), str(result.get("title", ""))
        snippet = str(result.get("snippet", ""))
        if not is_registry_url(url) or not names_match(company, title, snippet):
            continue
        facts.matched_urls.append(url)
        before = {k: getattr(facts, k) for k in FIELDS}
        fill(facts, snippet + " " + title + " " + url)
        for key in FIELDS:
            if before[key] is None and getattr(facts, key) is not None:
                facts.sources[key] = url
    return facts


def names_match(company: str, title: str, snippet: str) -> bool:
    # registry titles look like "OASIS CORPCARE PRIVATE LIMITED - ZaubaCorp"
    head = re.split(r"\s[-|]\s|\s-\s", title)[0]
    core = normalize_company(company)
    return similarity(company, head) >= NAME_MATCH or (
        bool(core) and core in normalize_company(snippet)
    )


def fill(facts: RegistryFacts, text: str) -> None:
    # first source to state a field wins; later ones only fill gaps
    if facts.cin is None and (m := CIN.search(text)):
        facts.cin = m.group(1)
    if facts.incorporated is None and (m := INCORPORATED.search(text)):
        facts.incorporated = parse_date(m.group(1))
    if facts.status is None and (m := STATUS.search(text)):
        facts.status = m.group(1).lower()
    if facts.authorised_paise is None and (m := AUTHORISED.search(text)):
        facts.authorised_paise = money(m.group(1))
    if facts.paid_up_paise is None and (m := PAID_UP.search(text)):
        facts.paid_up_paise = money(m.group(1))
    if facts.business_line is None and (m := BUSINESS.search(text)):
        facts.business_line = m.group(1).strip()
    if facts.last_agm is None and (m := AGM.search(text)):
        facts.last_agm = parse_date(m.group(1))
    if facts.last_balance_sheet is None and (m := BALANCE_SHEET.search(text)):
        facts.last_balance_sheet = parse_date(m.group(1))
    if facts.city is None and (m := CITY.search(text)):
        facts.city = m.group(1).strip()


def money(text: str) -> int | None:
    try:
        return parse_inr(text)
    except MoneyParseError:
        return None
