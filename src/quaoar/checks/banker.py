# merchant banker track record: SEBI orders naming the banker, and orders naming its past issuers
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit

from quaoar.checks.base import SearchPort, evidence, results
from quaoar.checks.registry import registry_core
from quaoar.domain.claims import LeadManagerClaim, PastIssueClaim
from quaoar.domain.findings import Evidence
from quaoar.domain.names import normalize_company

MAX_PAST_ISSUES = 5
SEBI_HOST = "sebi.gov.in"
MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
ORDER_PATH = re.compile(r"/enforcement/orders/([a-z]{3})-(\d{4})/")


@dataclass(slots=True)
class OrderHit:
    title: str
    url: str
    month: date | None
    evidence: Evidence


@dataclass(slots=True)
class BankerFindings:
    banker: str
    page: int
    banker_orders: list[OrderHit] = field(default_factory=list)
    past_issuers: list[str] = field(default_factory=list)
    issuer_orders: dict[str, list[OrderHit]] = field(default_factory=dict)


def banker_check(
    banker: LeadManagerClaim,
    past_issues: Sequence[PastIssueClaim],
    search: SearchPort,
    parent: str | None = None,
) -> BankerFindings:
    found = BankerFindings(banker.name, banker.page)
    found.banker_orders = sebi_orders(banker.name, search, parent)

    seen: set[str] = set()
    for issue in past_issues:
        key = normalize_company(issue.issuer)
        if key and key not in seen and len(seen) < MAX_PAST_ISSUES:
            seen.add(key)
            found.past_issuers.append(issue.issuer)
            found.issuer_orders[issue.issuer] = sebi_orders(issue.issuer, search, parent)
    return found


def sebi_orders(name: str, search: SearchPort, parent: str | None) -> list[OrderHit]:
    result = search.query("duckduckgo", {"q": f'"{registry_core(name)}" site:{SEBI_HOST}'}, parent)
    core = normalize_company(name)
    hits: list[OrderHit] = []
    for item in results(result, "organic_results"):
        url = str(item.get("link", ""))
        if not is_sebi_order(url) or core not in normalize_company(str(item.get("title", ""))):
            continue
        hits.append(
            OrderHit(str(item.get("title", "")), url, order_month(url), evidence(result, item))
        )
    return hits


def is_sebi_order(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return (host == SEBI_HOST or host.endswith("." + SEBI_HOST)) and bool(
        ORDER_PATH.search(parts.path)
    )


def order_month(url: str) -> date | None:
    # sebi order urls carry the month they were published in
    match = ORDER_PATH.search(urlsplit(url).path)
    if not match or match.group(1) not in MONTHS:
        return None
    return date(int(match.group(2)), MONTHS[match.group(1)], 1)


def before(hits: Sequence[OrderHit], cutoff: date | None) -> list[OrderHit]:
    if cutoff is None:
        return list(hits)
    return [h for h in hits if h.month is not None and h.month <= cutoff.replace(day=1)]
