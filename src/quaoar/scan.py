# one scan end to end: pages, sections, claims, checks, rules, card; every stage is an event
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from quaoar.checks.banker import banker_check
from quaoar.checks.base import SearchPort
from quaoar.checks.book import Investigator
from quaoar.checks.footprint import footprint
from quaoar.checks.litigation import litigation_check
from quaoar.checks.site import MAX_PLACES, site_visit
from quaoar.checks.vendor import vendor_xray
from quaoar.clock import ClockPort
from quaoar.domain.claims import (
    DisclosedCaseClaim,
    LeadManagerClaim,
    PastIssueClaim,
    PlaceClaim,
    PromoterClaim,
    QuoteClaim,
)
from quaoar.domain.findings import Signal
from quaoar.domain.ids import stable_id
from quaoar.events import Emitter
from quaoar.prospectus.acquire import Prospectus
from quaoar.prospectus.extract import ClaimSource, Extraction, extract_claims
from quaoar.prospectus.meta import prospectus_date
from quaoar.prospectus.pdf import Page, read_pages
from quaoar.prospectus.sections import SectionMap, locate_sections
from quaoar.scoring.banker_rules import banker_signals
from quaoar.scoring.card import Card, build_card
from quaoar.scoring.footprint_rules import footprint_signals
from quaoar.scoring.litigation_rules import litigation_signals
from quaoar.scoring.rules import RULESET_VERSION, vendor_signals
from quaoar.scoring.site_rules import site_signals

ISSUER_LINE = re.compile(r"^[A-Z][A-Z0-9&.,' ()-]{2,80}\bLIMITED$")


@dataclass(frozen=True, slots=True)
class ScanResult:
    scan_id: str
    company: str
    sections: SectionMap
    extraction: Extraction
    signals: list[Signal]
    card: Card


def scan_id_for(prospectus: Prospectus) -> str:
    # same pdf and ruleset give the same id, which is what lets a scan resume
    return "q" + stable_id({"pdf": prospectus.sha256, "ruleset": RULESET_VERSION})[:11]


def run_scan(
    prospectus: Prospectus,
    *,
    search: SearchPort,
    claims: ClaimSource,
    emit: Emitter,
    clock: ClockPort,
    cutoff: date | None = None,
    investigator: Investigator | None = None,
    point_in_time: bool = True,
) -> ScanResult:
    scan_id = scan_id_for(prospectus)
    root = emit(
        "stage", {"name": "intake", "bytes": prospectus.size, "sha256": prospectus.sha256[:16]}
    )
    pages = timed(emit, clock, root, "pages", lambda: read_pages(prospectus.path))
    company = issuer_name(pages)
    cutoff = choose_cutoff(pages, cutoff, emit, root, point_in_time=point_in_time)
    sections = timed(emit, clock, root, "sections", lambda: locate_sections(pages))
    extraction = read_claims(pages, sections, claims, emit, root)

    signals = vendor_stage(extraction, search, emit, root, cutoff, investigator)
    signals += site_stage(company, extraction, search, emit, root, investigator)
    signals += banker_stage(extraction, search, emit, root, cutoff)
    signals += litigation_stage(company, extraction, search, emit, root, cutoff)
    check = emit("stage", {"name": "footprint", "subject": company}, root)
    signals += footprint_signals(footprint(company, search, check), cutoff)
    for signal in signals:
        emit(
            "signal",
            {"rule": signal.rule, "status": signal.status.value, "text": signal.text[:300]},
            root,
        )

    card = build_card(scan_id, company, signals)
    emit(
        "card",
        {
            "consistent": card.consistent,
            "inconsistent": card.inconsistent,
            "unverified": card.unverified,
        },
        root,
    )
    return ScanResult(scan_id, company, sections, extraction, signals, card)


def choose_cutoff(
    pages: list[Page], given: date | None, emit: Emitter, root: str, *, point_in_time: bool
) -> date | None:
    # by default evidence is read as of the prospectus date, so later news can't change the card
    cutoff = given or (prospectus_date(pages) if point_in_time else None)
    shown = cutoff.isoformat() if cutoff else "none (evidence as of today)"
    emit("stage", {"name": "cutoff", "date": shown}, root)
    return cutoff


def read_claims(
    pages: list[Page], sections: SectionMap, claims: ClaimSource, emit: Emitter, root: str
) -> Extraction:
    found = ", ".join(sorted(sections.sections))
    emit(
        "stage", {"name": "sections", "found": found, "missing": ", ".join(sections.missing)}, root
    )
    stage = emit("stage", {"name": "claims"}, root)
    extraction = extract_claims(pages, sections, claims, emit, stage)
    counts = ", ".join(f"{k} {len(v)}" for k, v in extraction.claims.items())
    emit("stage", {"name": "claims", "counts": counts}, stage)
    return extraction


def vendor_stage(
    extraction: Extraction,
    search: SearchPort,
    emit: Emitter,
    root: str,
    cutoff: date | None,
    investigator: Investigator | None = None,
) -> list[Signal]:
    signals: list[Signal] = []
    for quote in extraction.claims.get("quotes", []):
        if isinstance(quote, QuoteClaim):
            check = emit("stage", {"name": "vendor", "subject": quote.vendor}, root)
            signals += vendor_signals(vendor_xray(quote, search, check, investigator), cutoff)
    return signals


def site_stage(
    company: str,
    extraction: Extraction,
    search: SearchPort,
    emit: Emitter,
    root: str,
    investigator: Investigator | None,
) -> list[Signal]:
    signals: list[Signal] = []
    places = [c for c in extraction.claims.get("places", []) if isinstance(c, PlaceClaim)]
    for place in places[:MAX_PLACES]:
        check = emit("stage", {"name": "site", "subject": f"{place.role} {place.city}"}, root)
        signals += site_signals(site_visit(company, place, search, check, investigator))
    return signals


def banker_stage(
    extraction: Extraction, search: SearchPort, emit: Emitter, root: str, cutoff: date | None
) -> list[Signal]:
    managers = [
        c for c in extraction.claims.get("lead_managers", []) if isinstance(c, LeadManagerClaim)
    ]
    past = [c for c in extraction.claims.get("past_issues", []) if isinstance(c, PastIssueClaim)]
    if not managers:
        return []
    check = emit("stage", {"name": "banker", "subject": managers[0].name}, root)
    return banker_signals(banker_check(managers[0], past, search, check), cutoff)


def litigation_stage(
    company: str,
    extraction: Extraction,
    search: SearchPort,
    emit: Emitter,
    root: str,
    cutoff: date | None,
) -> list[Signal]:
    cases = [c for c in extraction.claims.get("cases", []) if isinstance(c, DisclosedCaseClaim)]
    promoters = [c for c in extraction.claims.get("promoters", []) if isinstance(c, PromoterClaim)]
    # a prospectus with no litigation section located gives nothing to compare against
    if not extraction.claims.get("cases") and not extraction.claims.get("promoters"):
        return []
    check = emit("stage", {"name": "litigation", "subject": company}, root)
    return litigation_signals(litigation_check(company, 1, cases, promoters, search, check), cutoff)


def timed[T](emit: Emitter, clock: ClockPort, parent: str, name: str, run: Callable[[], T]) -> T:
    start = clock.ns()
    value = run()
    emit("stage", {"name": name, "ms": round((clock.ns() - start) / 1e6, 3)}, parent)
    return value


def issuer_name(pages: list[Page]) -> str:
    # the cover names the issuer in capitals ending in LIMITED
    for page in pages[:2]:
        for line in page.text.splitlines():
            line = " ".join(line.split())
            if ISSUER_LINE.match(line):
                return line
    return "Unnamed issuer"
