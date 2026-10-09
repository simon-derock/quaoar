# what every check needs: a search port and a way to turn results into evidence
from collections.abc import Mapping
from datetime import date
from typing import Protocol

from pydantic import JsonValue

from quaoar.domain.dates import parse_date
from quaoar.domain.findings import Evidence
from quaoar.guard.pii import mask_pii
from quaoar.guard.text import clean_text
from quaoar.serp.client import SerpResult

SNIPPET_CHARS = 300


class SearchPort(Protocol):
    def query(
        self, engine: str, params: Mapping[str, object], parent: str | None = None
    ) -> SerpResult: ...


def evidence(result: SerpResult, item: Mapping[str, object]) -> Evidence:
    # third-party text is cleaned and masked before anyone can see it
    snippet = safe(str(item.get("snippet") or item.get("address") or ""))[:SNIPPET_CHARS]
    return Evidence(
        engine=result.engine,
        request=result.request_hash[:16],
        search_id=result.search_id,
        url=str(item.get("link") or item.get("website") or ""),
        title=safe(str(item.get("title", "")))[:200],
        snippet=snippet,
        published=item_date(item),
    )


def safe(text: str) -> str:
    return mask_pii(clean_text(text).text).text


def results(result: SerpResult, key: str) -> list[dict[str, JsonValue]]:
    found = result.body.get(key)
    if isinstance(found, dict):
        return [found]
    if isinstance(found, list):
        return [item for item in found if isinstance(item, dict)]
    return []


def item_date(item: Mapping[str, object]) -> date | None:
    # serpapi's news "date" is month-first (12/04/2024 is 4 December), so the iso field wins
    iso = item.get("iso_date")
    if isinstance(iso, str) and len(iso) >= 10:
        try:
            return date.fromisoformat(iso[:10])
        except ValueError:
            return None
    raw = item.get("date")
    return parse_date(raw) if isinstance(raw, str) else None
