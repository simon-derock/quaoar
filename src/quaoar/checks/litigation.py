# litigation the prospectus did not mention: legal-site hits for the issuer and its promoters
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit

from quaoar.checks.banker import order_month
from quaoar.checks.base import SearchPort, evidence, results
from quaoar.checks.registry import registry_core
from quaoar.domain.claims import DisclosedCaseClaim, PromoterClaim
from quaoar.domain.dates import parse_date
from quaoar.domain.findings import Evidence
from quaoar.domain.names import normalize_company

LEGAL_SITES = "(site:sebi.gov.in OR site:indiankanoon.org OR site:ibbi.gov.in)"
LEGAL_DOMAINS = ("sebi.gov.in", "indiankanoon.org", "ibbi.gov.in")
MAX_PROMOTERS = 3
NOISE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class Matter:
    subject: str
    about_issuer: bool
    title: str
    url: str
    when: date | None
    disclosed: bool
    evidence: Evidence


@dataclass(slots=True)
class LitigationFindings:
    issuer: str
    page: int | None
    subjects: list[str] = field(default_factory=list)
    matters: list[Matter] = field(default_factory=list)
    disclosed_count: int = 0


def litigation_check(
    issuer: str,
    issuer_page: int | None,
    disclosed: Sequence[DisclosedCaseClaim],
    promoters: Sequence[PromoterClaim],
    search: SearchPort,
    parent: str | None = None,
) -> LitigationFindings:
    found = LitigationFindings(issuer, issuer_page, disclosed_count=len(disclosed))
    names = [issuer, *dict.fromkeys(p.name for p in promoters)][: MAX_PROMOTERS + 1]
    refs = {squash(c.case_ref) for c in disclosed if c.case_ref.strip()}
    issuer_core = normalize_company(issuer)

    for name in names:
        found.subjects.append(name)
        result = search.query("duckduckgo", {"q": f'"{registry_core(name)}" {LEGAL_SITES}'}, parent)
        core = normalize_company(name)
        for item in results(result, "organic_results"):
            url, title = str(item.get("link", "")), str(item.get("title", ""))
            if not is_legal_url(url) or core not in normalize_company(title):
                continue
            text = f"{title} {item.get('snippet', '')} {url}"
            # a person's name alone can't tell two people apart, so a promoter hit must also name the issuer
            if name != issuer and issuer_core not in normalize_company(text):
                continue
            found.matters.append(
                Matter(name, name == issuer, title, url, matter_date(url, title), any(r in squash(text) for r in refs), evidence(result, item))
            )  # fmt: skip
    return found


def is_legal_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in LEGAL_DOMAINS)


def matter_date(url: str, title: str) -> date | None:
    # indian kanoon titles end "... on 24 January, 2025"; sebi urls carry the month
    return parse_date(title) or order_month(url)


def squash(text: str) -> str:
    return NOISE.sub("", text.lower())


def undisclosed_before(found: LitigationFindings, cutoff: date | None) -> list[Matter]:
    out = []
    for matter in found.matters:
        if matter.disclosed:
            continue
        if cutoff is not None and (matter.when is None or matter.when > cutoff):
            continue
        out.append(matter)
    return out
