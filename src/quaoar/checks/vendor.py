# vendor x-ray (the Trafiksol test): is the company quoting for the IPO money real and sized for it
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from quaoar.checks.base import SearchPort, evidence, results
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
from quaoar.domain.names import similarity

PLACE_MATCH = 0.85


@dataclass(slots=True)
class MapsFacts:
    found: bool = False
    title: str = ""
    city_area: str = ""
    open_state: str = ""
    unclaimed: bool = False
    reviews: int = 0


@dataclass(slots=True)
class VendorFindings:
    vendor: str
    page: int
    quote_paise: int | None
    registry: RegistryFacts
    maps: MapsFacts
    registry_evidence: list[Evidence] = field(default_factory=list)
    maps_evidence: list[Evidence] = field(default_factory=list)


def vendor_xray(quote: QuoteClaim, search: SearchPort, parent: str | None = None) -> VendorFindings:
    registry = search.query(
        "duckduckgo", {"q": f'"{registry_core(quote.vendor)}" {REGISTRY_QUERY}'}, parent
    )
    # duckduckgo honours site:, but the domains are checked again here all the same
    organic = [
        r for r in results(registry, "organic_results") if is_registry_url(str(r.get("link", "")))
    ]
    facts = read_facts(quote.vendor, organic)
    found = VendorFindings(quote.vendor, quote.page, quote_paise(quote), facts, MapsFacts())
    found.registry_evidence = [
        evidence(registry, r) for r in organic if r.get("link") in facts.matched_urls
    ]

    place_query = f"{quote.vendor} {facts.city}" if facts.city else quote.vendor
    maps = search.query("google_maps", {"q": place_query, "type": "search"}, parent)
    best = best_place(quote.vendor, results(maps, "local_results") + results(maps, "place_results"))
    if best is not None:
        found.maps = maps_facts(best)
        found.maps_evidence = [evidence(maps, best)]
    return found


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
