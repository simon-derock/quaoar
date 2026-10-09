# the investigator's hands: five search tools that build their own queries, so the model can only
# choose terms; the site allowlist, budgets and de-duplication live here, in code
import re
from collections.abc import Callable
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import Field, JsonValue
from pydantic_ai import Tool

from quaoar.checks.base import SearchPort, results, safe
from quaoar.checks.book import EvidenceBook, Hit, ToolCall
from quaoar.checks.litigation import LEGAL_SITES, is_legal_url
from quaoar.checks.registry import REGISTRY_QUERY, is_registry_url
from quaoar.events import Emitter
from quaoar.guard.injection import scan_injection
from quaoar.guard.query import QueryRejectedError
from quaoar.serp.client import SerpError, SerpResult
from quaoar.serp.keys import KeysExhaustedError

Terms = Annotated[
    str,
    Field(
        min_length=2,
        max_length=120,
        description="search terms: company name words, a CIN, or a city; no quotes, no site: filters",
    ),
]
Why = Annotated[
    str,
    Field(
        min_length=3,
        max_length=200,
        description="one sentence: which gap this search closes and how it differs from earlier searches",
    ),
]

MAX_HITS_SHOWN = 6
LINE_CHARS = 230
OPERATORS = re.compile(r"\b(?:site|inurl|intitle|filetype|related|cache):\S*|[\"“”]", re.I)
BLOCKED = "no more searches are allowed: call finish now"

SPECS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # tool -> (engine, rule for building the query, result keys)
    "search_registry": ("duckduckgo", "registry", ("organic_results",)),
    "search_legal": ("duckduckgo", "legal", ("organic_results",)),
    "search_maps": ("google_maps", "maps", ("local_results", "place_results")),
    "search_news": ("google_news", "news", ("news_results",)),
    "search_web": ("google", "web", ("organic_results",)),
}
DESCRIPTIONS = {
    "search_registry": "Search company-registry pages (Zauba, Tofler, InstaFinancials) for a company. Use name words, then city or CIN.",
    "search_legal": "Search SEBI, Indian Kanoon and IBBI pages that name a company. Company names only.",
    "search_maps": "Search Google Maps for a business. Try 'name city', then the distinctive words alone.",
    "search_news": "Search Google News for dated coverage of a company.",
    "search_web": "Search the open web for a company page. Last resort; prefer the specific tools.",
}


class Toolbox:
    def __init__(
        self,
        search: SearchPort,
        book: EvidenceBook,
        emit: Emitter | None,
        parent: str | None,
        *,
        max_credits: int,
        max_searches: int,
        running_numbers: bool = False,
    ) -> None:
        self._search, self.book, self._emit, self._parent = search, book, emit, parent
        self._max_credits, self._max_searches = max_credits, max_searches
        # the analyst cites results as S1, S2 ... across all its searches, so numbering carries on
        self._running = running_numbers
        self._seen: set[tuple[str, str]] = set()

    def tools(self, names: tuple[str, ...]) -> list[Tool]:
        # one bound function per tool, so each has its own name, schema and description
        return [
            Tool(self._function(name), name=name, description=DESCRIPTIONS[name]) for name in names
        ]

    def dispatch(self, call: ToolCall) -> str:
        return self.run(call.tool, call.args.get("terms", ""), call.why)

    def run(self, tool: str, terms: str, why: str) -> str:
        engine, kind, keys = SPECS[tool]
        clean_terms = " ".join(OPERATORS.sub(" ", safe(terms)).split())[:120]
        signature = (tool, clean_terms.casefold())
        self.book.calls.append(
            ToolCall(tool=tool, args={"terms": clean_terms}, why=safe(why)[:200])
        )
        self.book.steps += 1

        if len(clean_terms) < 2:
            return "<results>empty search terms</results>"
        if signature in self._seen:
            return "<results>refused: you already ran this exact search; change the terms</results>"
        if self.book.steps > self._max_searches or self.book.credits >= self._max_credits:
            return f"<results>{BLOCKED}</results>"
        self._seen.add(signature)

        try:
            result = self._search.query(engine, query_params(kind, clean_terms), self._parent)
        except QueryRejectedError as exc:
            return f"<results>search rejected ({exc.rule}); rephrase with plain company words</results>"
        except (SerpError, KeysExhaustedError):
            return f"<results>search unavailable; {BLOCKED}</results>"
        self.book.searches += 1
        return self._observe(tool, kind, keys, result, clean_terms, why)

    def _function(self, name: str) -> Callable[[Terms, Why], str]:
        def call(terms: Terms, why: Why) -> str:
            return self.run(name, terms, why)

        return call

    def _observe(
        self, tool: str, kind: str, keys: tuple[str, ...], result: SerpResult, terms: str, why: str
    ) -> str:
        self.book.credits += result.credits
        items = [item for key in keys for item in results(result, key)]
        accepted = [item for item in items if accepts(kind, item)]
        first = len(self.book.hits) + 1 if self._running else 1
        for item in accepted:
            self.book.hits.append(Hit(tool, result, item))
        lines = [
            describe(n, kind, item) for n, item in enumerate(accepted[:MAX_HITS_SHOWN], start=first)
        ]
        body = "\n".join(lines) if lines else "no results"
        ignored = len(items) - len(accepted)
        if ignored:
            body += f"\n({ignored} results ignored: not on the sites this tool covers)"
        flagged = scan_injection(body)
        if self._emit is not None:
            self._emit(
                "agent",
                {
                    "tool": tool,
                    "terms": terms,
                    "why": safe(why)[:200],
                    "hits": len(accepted),
                    "credits": result.credits,
                    "cached": result.cached,
                    "latency_ms": round(result.latency_ns / 1e6, 3),
                    "flagged": ", ".join(h.rule for h in flagged),
                },
                self._parent,
            )
        used = f"credits used {self.book.credits}/{self._max_credits}, searches {self.book.steps}/{self._max_searches}"
        return f'<results tool="{tool}" {used}>\n{body}\n</results>'


def query_params(kind: str, terms: str) -> dict[str, str]:
    if kind == "registry":
        return {"q": f'"{terms}" {REGISTRY_QUERY}'}
    if kind == "legal":
        return {"q": f'"{terms}" {LEGAL_SITES}'}
    if kind == "maps":
        return {"q": terms, "type": "search"}
    return {"q": terms}


def accepts(kind: str, item: dict[str, JsonValue]) -> bool:
    link = str(item.get("link", ""))
    if kind == "registry":
        return is_registry_url(link)
    if kind == "legal":
        return is_legal_url(link)
    return True


def describe(number: int, kind: str, item: dict[str, JsonValue]) -> str:
    title = safe(str(item.get("title", "")))[:90]
    if kind == "maps":
        detail = " | ".join(
            safe(str(item[k]))[:70] for k in ("type", "address", "open_state") if item.get(k)
        )
        return f"{number}. {title} | {detail}"[:LINE_CHARS]
    host = (urlsplit(str(item.get("link", ""))).hostname or "").removeprefix("www.")
    when = f" ({item['date']})" if item.get("date") else ""
    snippet = safe(str(item.get("snippet", "")))[:150]
    return f"{number}. {title} | {host}{when} | {snippet}"[:LINE_CHARS]
