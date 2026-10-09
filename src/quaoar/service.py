# the one way to run a scan from a path or url; cli and mcp both call this
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from quaoar.agent.loop import AgentInvestigator
from quaoar.analyst.agent import Analyst
from quaoar.clock import SystemClock
from quaoar.config import Settings, all_secrets, load_settings
from quaoar.events import Emitter, Event, EventSink, JournalSink
from quaoar.guard.secrets import SecretRedactor
from quaoar.llm.client import LlmClient
from quaoar.prospectus.acquire import Prospectus, from_path, from_url
from quaoar.prospectus.extract import Extraction
from quaoar.prospectus.pdf import read_pages
from quaoar.prospectus.sections import locate_sections
from quaoar.replay import ReplayBundleError, load_replay, replay_home
from quaoar.scan import ScanResult, read_claims, run_scan, scan_id_for
from quaoar.scoring.card import Card
from quaoar.serp.client import CreditBudget, LedgerClient, account_lookup
from quaoar.serp.keys import KeyPool
from quaoar.serp.ledger import Ledger


@dataclass(frozen=True, slots=True)
class Runtime:
    settings: Settings
    ledger: Ledger
    http: httpx.Client


@dataclass(frozen=True, slots=True)
class Executed:
    result: ScanResult
    credits: int
    folder: Path


def make_runtime(env_file: Path = Path(".env")) -> Runtime:
    settings = load_settings(env_file=env_file)
    return Runtime(settings, Ledger(settings.home), httpx.Client())


def intake(source: str, runtime: Runtime) -> Prospectus:
    if source.startswith(("https://", "http://")):
        return from_url(source, runtime.settings.home / "pdfs", runtime.http)
    return from_path(Path(source))


def scan_folder(runtime: Runtime, scan_id: str) -> Path:
    return runtime.settings.home / "scans" / scan_id


def execute(
    prospectus: Prospectus,
    runtime: Runtime,
    extra_sinks: Sequence[EventSink] = (),
    max_credits: int = 0,
    cutoff: date | None = None,
    *,
    mode: str = "agent",
    point_in_time: bool = True,
) -> Executed:
    scan_id = scan_id_for(prospectus)
    folder = scan_folder(runtime, scan_id)
    clock = SystemClock()
    sinks: list[EventSink] = [JournalSink(folder / "events.jsonl", fresh=True), *extra_sinks]
    redact = SecretRedactor(all_secrets(runtime.settings)).redact
    emit = Emitter(scan_id, Tee(sinks), clock, scrub=lambda text: redact(text).text)

    budget = CreditBudget(max_credits or runtime.settings.max_credits_per_scan)
    pool = KeyPool(
        runtime.settings.serpapi_keys, runtime.settings.key_reserve, account_lookup(runtime.http)
    )
    search = LedgerClient(
        ledger=runtime.ledger,
        http=runtime.http,
        clock=clock,
        budget=budget,
        pool=pool,
        emit=emit,
        scan=scan_id,
    )
    claims = LlmClient(
        ledger=runtime.ledger,
        clock=clock,
        model_name=runtime.settings.cohere_model,
        keys=runtime.settings.cohere_keys,
        emit=emit,
    )
    investigator = AgentInvestigator(claims, search, emit) if mode == "agent" else None
    result = run_scan(
        prospectus,
        search=search,
        claims=claims,
        emit=emit,
        clock=clock,
        cutoff=cutoff,
        investigator=investigator,
        point_in_time=point_in_time,
    )
    save(folder, result)
    return Executed(result, budget.spent, folder)


def save(folder: Path, result: ScanResult) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "card.json").write_text(result.card.model_dump_json(indent=2), encoding="utf-8")
    claims = {
        task: [c.model_dump() for c in items] for task, items in result.extraction.claims.items()
    }
    (folder / "claims.json").write_text(json.dumps(claims, indent=2, default=str), encoding="utf-8")


ASK_CREDITS = 3
CARD_REF = re.compile(r"^[a-z0-9-]{1,64}$")


class CardNotFoundError(LookupError):
    pass


def find_card(ref: str, runtime: Runtime) -> Card:
    # a recorded case by name, or a scan finished on this machine by its id
    if not CARD_REF.match(ref):
        raise CardNotFoundError(f"{ref!r} is not a case name or scan id")
    saved = scan_folder(runtime, ref) / "card.json"
    if saved.is_file():
        return Card.model_validate_json(saved.read_text(encoding="utf-8"))
    try:
        return load_replay(replay_home() / ref)[1]
    except ReplayBundleError:
        raise CardNotFoundError(f"no recorded case or saved scan called {ref!r}") from None


def make_analyst(runtime: Runtime, sinks: Sequence[EventSink] = ()) -> Analyst:
    # with no model or search keys the analyst still answers, from the card alone
    settings = runtime.settings
    if not settings.cohere_keys or not settings.serpapi_keys:
        return Analyst(None, None)
    clock = SystemClock()
    redact = SecretRedactor(all_secrets(settings)).redact
    emit = Emitter("ask", Tee(sinks), clock, scrub=lambda text: redact(text).text)
    pool = KeyPool(settings.serpapi_keys, settings.key_reserve, account_lookup(runtime.http))
    search = LedgerClient(
        ledger=runtime.ledger, http=runtime.http, clock=clock,
        budget=CreditBudget(ASK_CREDITS), pool=pool, emit=emit, scan="ask",
    )  # fmt: skip
    llm = LlmClient(
        ledger=runtime.ledger, clock=clock, model_name=settings.cohere_model,
        keys=settings.cohere_keys, emit=emit,
    )  # fmt: skip
    return Analyst(llm, search, emit)


def read_only(prospectus: Prospectus, runtime: Runtime) -> Extraction:
    # claims only, no searches: what a prospectus says, for comparing two versions of it
    clock = SystemClock()
    emit = Emitter("diff", Tee([]), clock)
    claims = LlmClient(
        ledger=runtime.ledger,
        clock=clock,
        model_name=runtime.settings.cohere_model,
        keys=runtime.settings.cohere_keys,
        emit=emit,
    )
    pages = read_pages(prospectus.path)
    root = emit("stage", {"name": "diff"})
    return read_claims(pages, locate_sections(pages), claims, emit, root)


class Tee:
    def __init__(self, sinks: Sequence[EventSink]) -> None:
        self._sinks = list(sinks)

    def write(self, event: Event) -> None:
        for sink in self._sinks:
            sink.write(event)
