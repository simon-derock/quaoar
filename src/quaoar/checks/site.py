# digital site visit: does the issuer's own office or factory exist on Maps, and what kind of place is it
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from quaoar.checks.base import SearchPort, evidence, results
from quaoar.checks.book import Goal, Handoff, Investigator
from quaoar.checks.vendor import MapsFacts, best_place, maps_facts
from quaoar.domain.claims import PlaceClaim
from quaoar.domain.findings import Evidence
from quaoar.serp.client import SerpResult

SITE_TOOLS = ("search_maps", "search_web")
MAX_PLACES = 3


@dataclass(slots=True)
class SiteFindings:
    issuer: str
    role: str
    locality: str
    city: str
    page: int
    maps: MapsFacts
    place_type: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    handoff: Handoff | None = None


def site_visit(
    issuer: str,
    place: PlaceClaim,
    search: SearchPort,
    parent: str | None = None,
    investigator: Investigator | None = None,
) -> SiteFindings:
    locality = "" if is_blank(place.locality) else place.locality
    query = f"{issuer} {locality} {place.city}".strip()
    found = SiteFindings(issuer, place.role, place.locality, place.city, place.page, MapsFacts())
    result = search.query("google_maps", {"q": query, "type": "search"}, parent)
    candidates = [
        (result, p) for p in results(result, "local_results") + results(result, "place_results")
    ]
    fill(found, issuer, candidates)

    if investigator is not None and not found.maps.found:
        known = {"role": f"the issuer's own {place.role.replace('_', ' ')}", "city": place.city}
        if locality:
            known["locality"] = locality
        book = investigator.run(
            Goal("place", issuer, known, ("maps",), (f"maps: {query}",), SITE_TOOLS), parent
        )
        candidates += [(h.result, h.item) for h in book.of("search_maps")]
        fill(found, issuer, candidates)
        found.handoff = book.handoff
    return found


def is_blank(text: str) -> bool:
    # prospectuses print "NIL" or "N.A." where an address field is empty
    return text.strip().strip(".").lower() in {"", "nil", "na", "n/a", "none", "-"}


def usable(place: PlaceClaim) -> bool:
    return not is_blank(place.city)


def fill(
    found: SiteFindings, issuer: str, candidates: Sequence[tuple[SerpResult, Mapping[str, object]]]
) -> None:
    best = best_place(issuer, [p for _, p in candidates])
    if best is None:
        return
    owner = next(res for res, p in candidates if p is best)
    found.maps = maps_facts(best)
    kind = best.get("type") or ""
    found.place_type = ", ".join(str(k) for k in kind) if isinstance(kind, list) else str(kind)
    found.evidence = [evidence(owner, best)]
