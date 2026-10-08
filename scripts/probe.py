# P0 probe: a handful of real searches through the ledger client, printed as field coverage only
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from quaoar.clock import SystemClock
from quaoar.config import load_settings
from quaoar.domain.names import similarity
from quaoar.serp.client import CreditBudget, LedgerClient, account_lookup
from quaoar.serp.keys import KeyPool
from quaoar.serp.ledger import Ledger

REGISTRY_SITES = "(site:zaubacorp.com OR site:instafinancials.com OR site:tofler.in)"
LEGAL_SITES = "(site:sebi.gov.in OR site:indiankanoon.org OR site:ibbi.gov.in)"
REGISTRY_FIELDS = {
    "paid_up": re.compile(r"paid[\s-]?up capital", re.I),
    "authorised": re.compile(r"authori[sz]ed (share )?capital", re.I),
    "status": re.compile(r"\b(status|strike off|struck off|active|dormant)\b", re.I),
    "balance_sheet": re.compile(r"balance sheet", re.I),
    "agm": re.compile(r"\bAGM\b|annual general meeting", re.I),
    "incorporated": re.compile(r"incorporated on|date of incorporation", re.I),
}

# (purpose, engine, params, entity used for name matching)
PROBES: list[tuple[str, str, dict[str, str], str]] = [
    (
        "R1 registry: trafiksol vendor",
        "google",
        {"q": f'"Oasis Corpcare" {REGISTRY_SITES}'},
        "Oasis Corpcare",
    ),
    (
        "R1 registry: issuer",
        "google",
        {"q": f'"Trafiksol ITS Technologies" {REGISTRY_SITES}'},
        "Trafiksol ITS Technologies",
    ),
    (
        "R1 registry: issuer 2",
        "google",
        {"q": f'"Droneacharya Aerial Innovations" {REGISTRY_SITES}'},
        "Droneacharya Aerial Innovations",
    ),
    (
        "R2 maps: trafiksol office",
        "google_maps",
        {"q": "Trafiksol ITS Technologies Noida", "type": "search"},
        "Trafiksol ITS Technologies",
    ),
    (
        "R2 maps: trafiksol vendor",
        "google_maps",
        {"q": "Oasis Corpcare Mumbai", "type": "search"},
        "Oasis Corpcare",
    ),
    (
        "R2 maps: droneacharya",
        "google_maps",
        {"q": "Droneacharya Aerial Innovations Pune", "type": "search"},
        "Droneacharya Aerial Innovations",
    ),
    (
        "R2 maps: synoptics",
        "google_maps",
        {"q": "Synoptics Technologies Navi Mumbai", "type": "search"},
        "Synoptics Technologies",
    ),
    (
        "R2 maps: varanium",
        "google_maps",
        {"q": "Varanium Cloud Mumbai", "type": "search"},
        "Varanium Cloud",
    ),
    (
        "LT legal: synoptics",
        "google",
        {"q": f'"Synoptics Technologies" {LEGAL_SITES}'},
        "Synoptics Technologies",
    ),
    (
        "BK banker orders",
        "google",
        {"q": '"First Overseas Capital" site:sebi.gov.in'},
        "First Overseas Capital",
    ),
    (
        "BK banker past issue",
        "google",
        {"q": '"Sameera Agro and Infra" site:sebi.gov.in'},
        "Sameera Agro and Infra",
    ),
    ("LT news: trafiksol", "google_news", {"q": "Trafiksol IPO SEBI"}, "Trafiksol"),
    ("HY youtube hype", "youtube", {"search_query": "Trafiksol IPO GMP"}, "Trafiksol"),
    (
        "R4 ticker lookup",
        "google",
        {"q": "Droneacharya Aerial Innovations share price BSE"},
        "Droneacharya",
    ),
]


def main() -> None:
    settings = load_settings(env_file=Path(".env"))
    http = httpx.Client()
    client = LedgerClient(
        ledger=Ledger(settings.home),
        http=http,
        clock=SystemClock(),
        budget=CreditBudget(int(sys.argv[1]) if len(sys.argv) > 1 else 30),
        pool=KeyPool(settings.serpapi_keys, settings.key_reserve, account_lookup(http)),
        scan="probe-20261009",
    )
    rows = [probe(client, *item) for item in PROBES]
    out = Path("results") / f"probe-{datetime.now(UTC):%Y%m%d}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        sys.stdout.write(json.dumps(row) + "\n")


def probe(
    client: LedgerClient, purpose: str, engine: str, params: dict[str, str], entity: str
) -> dict[str, object]:
    result = client.query(engine, params)
    row: dict[str, object] = {
        "purpose": purpose,
        "engine": engine,
        "status": result.status,
        "credits": result.credits,
        "cached": result.cached,
    }
    row.update(organic_summary(result.body, entity))
    row.update(places_summary(result.body, entity))
    row.update(items_summary(result.body))
    return row


def organic_summary(body: dict[str, Any], entity: str) -> dict[str, object]:
    organic = [r for r in body.get("organic_results") or [] if isinstance(r, dict)]
    if not organic:
        return {}
    snippets = " ".join(str(r.get("snippet", "")) for r in organic)
    summary: dict[str, object] = {
        "results": len(organic),
        "domains": sorted({str(r.get("displayed_link", ""))[:40] for r in organic})[:6],
        "registry_fields": sorted(k for k, p in REGISTRY_FIELDS.items() if p.search(snippets)),
        "dated_results": sum(1 for r in organic if r.get("date")),
        "best_title_match": round(
            max(similarity(entity, str(r.get("title", ""))) for r in organic), 2
        ),
    }
    answer = body.get("answer_box") or body.get("knowledge_graph")
    if isinstance(answer, dict):
        summary["answer_keys"] = sorted(answer)[:12]
    return summary


def places_summary(body: dict[str, Any], entity: str) -> dict[str, object]:
    local = body.get("local_results") or body.get("place_results")
    places = [p for p in (local if isinstance(local, list) else [local]) if isinstance(p, dict)]
    if not places:
        return {}
    return {
        "places": len(places),
        "best_place_match": round(
            max(similarity(entity, str(p.get("title", ""))) for p in places), 2
        ),
        "place_types": sorted({str(p.get("type", "")) for p in places})[:5],
        "permanently_closed": sum(
            1 for p in places if "permanently" in str(p.get("open_state", "")).lower()
        ),
        "unclaimed": sum(1 for p in places if p.get("unclaimed_listing")),
        "with_reviews": sum(1 for p in places if p.get("reviews")),
    }


def items_summary(body: dict[str, Any]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for key in ("news_results", "video_results"):
        items = [i for i in body.get(key) or [] if isinstance(i, dict)]
        if items:
            summary[key] = len(items)
            summary["dated_items"] = sum(
                1 for i in items if i.get("date") or i.get("published_date")
            )
    return summary


if __name__ == "__main__":
    main()
