# quaoar command line: scripted commands over the same core the mcp server and web console use
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.markup import escape

from quaoar.clock import SystemClock
from quaoar.config import Settings, all_secrets, load_settings
from quaoar.events import Emitter, Event, EventSink, JournalSink
from quaoar.guard.secrets import SecretRedactor
from quaoar.guard.text import clean_text
from quaoar.llm.client import LlmClient
from quaoar.prospectus.acquire import IntakeError, Prospectus, from_path, from_url
from quaoar.replay import ReplayBundleError, export_scan, load_replay
from quaoar.scan import ScanResult, run_scan, scan_id_for
from quaoar.scoring.card import MARKS, Card, headline
from quaoar.serp.client import CreditBudget, CreditBudgetExceededError, LedgerClient, account_lookup
from quaoar.serp.keys import KeyPool, KeysExhaustedError
from quaoar.serp.ledger import Ledger

app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="Check every IPO before you apply."
)
ledger_app = typer.Typer(no_args_is_help=True, help="The local evidence ledger.")
keys_app = typer.Typer(no_args_is_help=True, help="SerpApi key status.")
app.add_typer(ledger_app, name="ledger")
app.add_typer(keys_app, name="keys")
console = Console(highlight=False)

EXIT_INPUT, EXIT_PARTIAL = 2, 3


@dataclass(frozen=True, slots=True)
class Runtime:
    settings: Settings
    ledger: Ledger
    http: httpx.Client


# --- commands ---


@app.command()
def scan(
    source: str = typer.Argument(..., help="prospectus pdf path or https url"),
    max_credits: int = typer.Option(0, help="SerpApi credit cap for this scan (0 = settings)"),
    cutoff: str = typer.Option("", help="prospectus date YYYY-MM-DD for staleness rules"),
    jsonl: bool = typer.Option(False, "--jsonl", help="print raw events instead of pretty lines"),
) -> None:
    runtime = make_runtime()
    try:
        prospectus = intake(source, runtime)
    except IntakeError as exc:
        console.print(f"[red]can't use that input:[/red] {escape(str(exc))}")
        raise typer.Exit(EXIT_INPUT) from None

    scan_id = scan_id_for(prospectus)
    folder = runtime.settings.home / "scans" / scan_id
    sinks: list[EventSink] = [JournalSink(folder / "events.jsonl"), ConsoleSink(raw=jsonl)]
    clock = SystemClock()
    redact = SecretRedactor(all_secrets(runtime.settings)).redact
    emit = Emitter(scan_id, TeeSink(sinks), clock, scrub=lambda text: redact(text).text)

    cap = max_credits or runtime.settings.max_credits_per_scan
    search, budget = search_client(runtime, emit, scan_id, cap)
    claims = LlmClient(
        ledger=runtime.ledger,
        clock=clock,
        model_name=runtime.settings.cohere_model,
        keys=runtime.settings.cohere_keys,
        emit=emit,
    )
    try:
        result = run_scan(
            prospectus,
            search=search,
            claims=claims,
            emit=emit,
            clock=clock,
            cutoff=date.fromisoformat(cutoff) if cutoff else None,
        )
    except (KeysExhaustedError, CreditBudgetExceededError) as exc:
        console.print(f"[yellow]stopped early:[/yellow] {escape(str(exc))}")
        raise typer.Exit(EXIT_PARTIAL) from None

    save(folder, result)
    print_card(result.card)
    console.print(f"\ncredits used: {budget.spent} · scan id: {scan_id} · saved to {folder}")


@app.command()
def card(scan_id: str) -> None:
    path = make_runtime().settings.home / "scans" / scan_id / "card.json"
    if not path.is_file():
        console.print(f"no saved card for {escape(scan_id)}")
        raise typer.Exit(EXIT_INPUT)
    print_card(Card.model_validate_json(path.read_text(encoding="utf-8")))


@app.command()
def export(scan_id: str, name: str) -> None:
    runtime = make_runtime()
    dest = Path("fixtures/replay") / name
    try:
        export_scan(runtime.settings.home / "scans" / scan_id, dest, all_secrets(runtime.settings))
    except ReplayBundleError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(EXIT_INPUT) from None
    console.print(f"replay bundle written to {dest}")


@app.command()
def replay(bundle: Path) -> None:
    try:
        events, saved = load_replay(bundle)
    except ReplayBundleError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(EXIT_INPUT) from None
    sink = ConsoleSink(raw=False)
    for event in events:
        sink.write(event)
    print_card(saved)


@ledger_app.command("stats")
def ledger_stats() -> None:
    stats = make_runtime().ledger.stats()
    console.print(f"credits by engine: {stats.credits_by_engine}")
    console.print(f"credits by key:    {stats.credits_by_key}")
    console.print(f"cache hit rate:    {stats.hit_rate:.0%}")
    console.print(f"live latency p50 {stats.live_p50_ms} ms · p95 {stats.live_p95_ms} ms")


@ledger_app.command("verify")
def ledger_verify() -> None:
    bad = make_runtime().ledger.blobs.verify_all()
    console.print(
        "every blob matches its hash" if not bad else f"{len(bad)} blobs failed: {bad[:5]}"
    )
    if bad:
        raise typer.Exit(1)


@keys_app.command("status")
def keys_status() -> None:
    runtime = make_runtime()
    pool = KeyPool(
        runtime.settings.serpapi_keys, runtime.settings.key_reserve, account_lookup(runtime.http)
    )
    for state in pool.status():
        console.print(f"key {state.fingerprint}: {state.left} searches left")


# --- wiring ---


def make_runtime() -> Runtime:
    settings = load_settings(env_file=Path(".env"))
    return Runtime(settings, Ledger(settings.home), httpx.Client())


def intake(source: str, runtime: Runtime) -> Prospectus:
    if source.startswith(("https://", "http://")):
        return from_url(source, runtime.settings.home / "pdfs", runtime.http)
    return from_path(Path(source))


def search_client(
    runtime: Runtime, emit: Emitter, scan_id: str, cap: int
) -> tuple[LedgerClient, CreditBudget]:
    budget = CreditBudget(cap)
    pool = KeyPool(
        runtime.settings.serpapi_keys, runtime.settings.key_reserve, account_lookup(runtime.http)
    )
    client = LedgerClient(
        ledger=runtime.ledger,
        http=runtime.http,
        clock=SystemClock(),
        budget=budget,
        pool=pool,
        emit=emit,
        scan=scan_id,
    )
    return client, budget


def save(folder: Path, result: ScanResult) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "card.json").write_text(result.card.model_dump_json(indent=2), encoding="utf-8")
    claims = {
        task: [c.model_dump() for c in items] for task, items in result.extraction.claims.items()
    }
    (folder / "claims.json").write_text(json.dumps(claims, indent=2, default=str), encoding="utf-8")


def print_card(card: Card) -> None:
    colours = {"checks out": "green", "doesn't match": "yellow", "couldn't find": "bright_black"}
    console.print(f"\n[bold]QUAOAR · {escape(card.company)}[/bold]")
    console.print(headline(card))
    for number, signal in enumerate(card.signals, start=1):
        mark = MARKS[signal.status]
        console.print(
            f"{number:>2}. [{colours.get(mark, 'white')}]{mark}[/] {escape(safe(signal.text))}"
        )
        for proof in signal.evidence[:1]:
            console.print(
                f"    proof: {escape(proof.url)} (search {escape(proof.search_id or '-')})"
            )
    console.print(f"\n{card.disclaimer}")


# --- event sinks ---


class TeeSink:
    def __init__(self, sinks: list[EventSink]) -> None:
        self._sinks = sinks

    def write(self, event: Event) -> None:
        for sink in self._sinks:
            sink.write(event)


class ConsoleSink:
    def __init__(self, *, raw: bool) -> None:
        self._raw = raw

    def write(self, event: Event) -> None:
        if self._raw:
            console.print(escape(event.model_dump_json()))
            return
        line = pretty(event)
        if line:
            console.print(line)


def pretty(event: Event) -> str:
    d = event.data
    if event.type == "serp":
        return f"  [cyan]search[/] {d['engine']} · {d['credits']} cr · {d['source']} · {d['latency_ms']} ms"
    if event.type == "llm":
        cost = "cache" if d["cached"] else f"{d['tokens_in']}+{d['tokens_out']} tok"
        return f"  [magenta]read[/] {d['task']} · {cost} · {d['latency_ms']} ms"
    if event.type == "stage":
        extra = " · ".join(f"{k} {escape(safe(str(v)))}" for k, v in d.items() if k != "name")
        return f"[bold]{d['name']}[/]" + (f" · {extra}" if extra else "")
    if event.type == "guard":
        return f"  [red]guard[/] {d['guard']} flagged {escape(str(d.get('rules', '')))} in {d['source']}"
    return ""


def safe(text: str) -> str:
    return clean_text(text).text
