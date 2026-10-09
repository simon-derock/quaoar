# vendor x-ray (the Trafiksol test): is the company quoting for the IPO money real and sized for it
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from pydantic import JsonValue

from quaoar.checks.base import SearchPort, evidence, results
from quaoar.checks.book import Goal, Handoff, Hit, Investigator
from quaoar.checks.litigation import LEGAL_SITES, is_legal_url, matter_date
from quaoar.checks.registry import (
    REGISTRY_QUERY,
    RegistryFacts,
    is_registry_url,
    read_facts,
    registry_core,
)
from quaoar.domain.claims import QuoteClaim
from quaoar.domain.findings import Evidence
from quaoar.domain.money import MoneyParseError, parse_inr
from quaoar.domain.names import normalize_company, similarity
from quaoar.serp.client import SerpResult

PLACE_MATCH = 0.85
VENDOR_TOOLS = ("search_registry", "search_maps", "search_web")


@dataclass(slots=True)
class MapsFacts:
    found: bool = False
    title: str = ""
    city_area: str = ""
    open_state: str = ""
    unclaimed: bool = False
    reviews: int = 0


@dataclass(slots=True)
class VendorMatter:
    title: str
    when: date | None
    evidence: Evidence


@dataclass(slots=True)
class VendorFindings:
    vendor: str
    page: int
    quote_paise: int | None
    registry: RegistryFacts
    maps: MapsFacts
    registry_evidence: list[Evidence] = field(default_factory=list)
    maps_evidence: list[Evidence] = field(default_factory=list)
    legal: list[VendorMatter] = field(default_factory=list)
    handoff: Handoff | None = None
    agent_searches: int = 0


@dataclass(slots=True)
class Pool:
    # every (search, item) the check has seen, from the fixed queries and from the agent alike
    registry: list[tuple[SerpResult, dict[str, JsonValue]]] = field(default_factory=list)
    maps: list[tuple[SerpResult, dict[str, JsonValue]]] = field(default_factory=list)
    legal: list[tuple[SerpResult, dict[str, JsonValue]]] = field(default_factory=list)

    def take(self, hits: Sequence[Hit]) -> None:
        for hit in hits:
            link = str(hit.item.get("link", ""))
            if is_registry_url(link):
                self.registry.append((hit.result, hit.item))
            elif is_legal_url(link):
                self.legal.append((hit.result, hit.item))
            elif hit.tool == "search_maps":
                self.maps.append((hit.result, hit.item))


def vendor_xray(
    quote: QuoteClaim,
    search: SearchPort,
    parent: str | None = None,
    investigator: Investigator | None = None,
) -> VendorFindings:
    core = registry_core(quote.vendor)
    pool = Pool()

    # fixed queries first: cheap, cached, and often enough
    registry = search.query("duckduckgo", {"q": f'"{core}" {REGISTRY_QUERY}'}, parent)
    pool.registry += [(registry, r) for r in results(registry, "organic_results")]
    city = read_facts(quote.vendor, [r for _, r in pool.registry]).city
    place_query = f"{quote.vendor} {city}" if city else quote.vendor
    maps = search.query("google_maps", {"q": place_query, "type": "search"}, parent)
    pool.maps += [
        (maps, r) for r in results(maps, "local_results") + results(maps, "place_results")
    ]
    legal = search.query("duckduckgo", {"q": f'"{core}" {LEGAL_SITES}'}, parent)
    pool.legal += [(legal, r) for r in results(legal, "organic_results")]

    found = assemble(quote, pool)
    gaps = vendor_gaps(found)
    if investigator is not None and gaps:
        done = (f'registry: "{core}"', f"maps: {place_query}", f'legal: "{core}"')
        goal = Goal("vendor", quote.vendor, known_facts(found), gaps, done, VENDOR_TOOLS)
        book = investigator.run(goal, parent)
        pool.take(book.hits)
        found = assemble(quote, pool)
        found.handoff, found.agent_searches = book.handoff, len(book.calls)
    return found


def assemble(quote: QuoteClaim, pool: Pool) -> VendorFindings:
    organic = [(res, r) for res, r in pool.registry if is_registry_url(str(r.get("link", "")))]
    facts = read_facts(quote.vendor, [r for _, r in organic])
    found = VendorFindings(quote.vendor, quote.page, quote_paise(quote), facts, MapsFacts())
    found.registry_evidence = [
        evidence(res, r) for res, r in organic if r.get("link") in facts.matched_urls
    ]

    best = best_place(quote.vendor, [r for _, r in pool.maps])
    if best is not None:
        owner = next(res for res, r in pool.maps if r is best)
        found.maps, found.maps_evidence = maps_facts(best), [evidence(owner, best)]

    core = normalize_company(quote.vendor)
    for res, r in pool.legal:
        link, title = str(r.get("link", "")), str(r.get("title", ""))
        if is_legal_url(link) and core in normalize_company(title):
            found.legal.append(VendorMatter(title, matter_date(link, title), evidence(res, r)))
    return found


def vendor_gaps(found: VendorFindings) -> tuple[str, ...]:
    gaps = []
    facts = found.registry
    if not facts.matched_urls or facts.paid_up_paise is None or facts.status is None:
        gaps.append("registry")
    if not found.maps.found:
        gaps.append("maps")
    return tuple(gaps)


def known_facts(found: VendorFindings) -> dict[str, str]:
    facts = found.registry
    known = {"role": "vendor named in the prospectus's objects of the issue"}
    if facts.city:
        known["city"] = facts.city
    if facts.cin:
        known["cin"] = facts.cin
    if facts.business_line:
        known["line of business"] = facts.business_line
    return known


def quote_paise(quote: QuoteClaim) -> int | None:
    try:
        return parse_inr(quote.amount_text, unit=quote.unit_text or None)
    except MoneyParseError:
        return None


def best_place(vendor: str, places: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    scored = [(similarity(vendor, str(p.get("title", ""))), p) for p in places]
    scored = [(score, p) for score, p in scored if score >= PLACE_MATCH]
    return max(scored, key=lambda pair: pair[0])[1] if scored else None


def maps_facts(place: Mapping[str, object]) -> MapsFacts:
    address = str(place.get("address", ""))
    # only the last two parts of an address are kept: area and city, never a door number
    city_area = ", ".join(part.strip() for part in address.split(",")[-2:]) if address else ""
    reviews = place.get("reviews")
    return MapsFacts(
        found=True,
        title=str(place.get("title", "")),
        city_area=city_area,
        open_state=str(place.get("open_state", "")),
        unclaimed=bool(place.get("unclaimed_listing")),
        reviews=reviews if isinstance(reviews, int) else 0,
    )
