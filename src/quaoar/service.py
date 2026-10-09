# the one way to run a scan from a path or url; cli and mcp both call this
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from quaoar.agent.loop import AgentInvestigator
from quaoar.clock import SystemClock
from quaoar.config import Settings, all_secrets, load_settings
from quaoar.events import Emitter, Event, EventSink, JournalSink
from quaoar.guard.secrets import SecretRedactor
from quaoar.llm.client import LlmClient
from quaoar.prospectus.acquire import Prospectus, from_path, from_url
from quaoar.scan import ScanResult, run_scan, scan_id_for
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


class Tee:
    def __init__(self, sinks: Sequence[EventSink]) -> None:
        self._sinks = list(sinks)

    def write(self, event: Event) -> None:
        for sink in self._sinks:
            sink.write(event)
