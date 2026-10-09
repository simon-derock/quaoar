# quaoar command line: scripted commands over the same core the mcp server and web console use
import sys
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from quaoar.config import all_secrets
from quaoar.events import Event
from quaoar.guard.text import clean_text
from quaoar.prospectus.acquire import IntakeError
from quaoar.prospectus.diff import Change, diff_claims
from quaoar.replay import ReplayBundleError, export_scan, find_case, load_replay, replay_home
from quaoar.scoring.card import MARKS, Card, headline
from quaoar.serp.client import CreditBudgetExceededError, account_lookup
from quaoar.serp.keys import KeyPool, KeysExhaustedError
from quaoar.service import execute, intake, make_runtime, read_only

app = typer.Typer(add_completion=False, help="Check every IPO before you apply.")
ledger_app = typer.Typer(no_args_is_help=True, help="The local evidence ledger.")
keys_app = typer.Typer(no_args_is_help=True, help="SerpApi key status.")
app.add_typer(ledger_app, name="ledger")
app.add_typer(keys_app, name="keys")
console = Console(highlight=False)
CONSOLE = console  # default output of print_card

EXIT_INPUT, EXIT_PARTIAL = 2, 3


# --- commands ---


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    # `quaoar` on its own opens the interactive terminal; subcommands still work as before
    if ctx.invoked_subcommand is None:
        start_terminal()


@app.command()
def scan(
    source: str = typer.Argument(..., help="prospectus pdf path or https url"),
    max_credits: int = typer.Option(0, help="SerpApi credit cap for this scan (0 = settings)"),
    cutoff: str = typer.Option(
        "", help="evidence date YYYY-MM-DD (default: the date printed on the prospectus)"
    ),
    now: bool = typer.Option(
        False, "--now", help="read evidence as of today instead of the prospectus date"
    ),
    jsonl: bool = typer.Option(False, "--jsonl", help="print raw events instead of pretty lines"),
    mode: str = typer.Option(
        "agent", help="agent: fill evidence gaps with a ReAct investigator; fixed: templates only"
    ),
) -> None:
    runtime = make_runtime()
    try:
        prospectus = intake(source, runtime)
    except IntakeError as exc:
        console.print(f"[red]can't use that input:[/red] {escape(str(exc))}")
        raise typer.Exit(EXIT_INPUT) from None

    try:
        done = execute(
            prospectus,
            runtime,
            [ConsoleSink(raw=jsonl)],
            max_credits,
            date.fromisoformat(cutoff) if cutoff else None,
            mode=mode,
            point_in_time=not now,
        )
    except IntakeError as exc:
        console.print(f"[red]can't use that input:[/red] {escape(str(exc))}")
        raise typer.Exit(EXIT_INPUT) from None
    except (KeysExhaustedError, CreditBudgetExceededError) as exc:
        console.print(f"[yellow]stopped early:[/yellow] {escape(str(exc))}")
        raise typer.Exit(EXIT_PARTIAL) from None

    print_card(done.result.card)
    console.print(
        f"\ncredits used: {done.credits} · scan id: {done.result.scan_id} · saved to {done.folder}"
    )


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
        events, saved = load_replay(find_case(bundle))
    except ReplayBundleError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(EXIT_INPUT) from None
    sink = ConsoleSink(raw=False)
    for event in events:
        sink.write(event)
    print_card(saved)


@app.command()
def diff(earlier: str, later: str) -> None:
    # draft vs red herring vs final: what the company changed between versions (no searches, no credits)
    runtime = make_runtime()
    try:
        old = read_only(intake(earlier, runtime), runtime).claims
        new = read_only(intake(later, runtime), runtime).claims
    except IntakeError as exc:
        console.print(f"[red]can't use that input:[/red] {escape(str(exc))}")
        raise typer.Exit(EXIT_INPUT) from None
    for line in render_changes(diff_claims(old, new)):
        console.print(escape(line))


def render_changes(changes: list[Change]) -> list[str]:
    if not changes:
        return [
            "no differences in vendors, matters, promoters, group companies, places or lead managers"
        ]
    return [
        f"{c.kind} · {c.text} (page {c.page_old or '-'} → {c.page_new or '-'})" for c in changes
    ]


@app.command()
def mcp() -> None:
    from quaoar.mcp_server import serve

    serve()


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    from quaoar.api.app import create_app

    settings = make_runtime().settings
    uvicorn.run(create_app(replay_home(), settings.cors_origin), host=host, port=port)


@app.command()
def comment(scan_id: str) -> None:
    from quaoar.scoring.comment import draft_comment

    path = make_runtime().settings.home / "scans" / scan_id / "card.json"
    if not path.is_file():
        console.print(f"no saved card for {escape(scan_id)}")
        raise typer.Exit(EXIT_INPUT)
    letter = draft_comment(Card.model_validate_json(path.read_text(encoding="utf-8")))
    if letter is None:
        console.print("nothing to comment on: no line in this card failed to match")
        return
    sys.stdout.write(letter)


@app.command()
def doctor() -> None:
    from quaoar.doctor import diagnose

    rows = diagnose(make_runtime())
    for ok, text in rows:
        console.print(f"[green]ok[/]  {escape(text)}" if ok else f"[red]!![/]  {escape(text)}")
    if not all(ok for ok, _ in rows):
        raise typer.Exit(1)


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


def print_card(card: Card, out: Console | None = None) -> None:
    console = out or CONSOLE
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
    for note in card.context:
        console.print(f"[bright_black]{escape(safe(note.text))}[/]")
    console.print(f"\n{card.disclaimer}")


# --- terminal ---


def start_terminal() -> None:
    from quaoar.terminal import Session, run

    runtime = make_runtime()

    def live(source: str, mode: str, budget: int) -> tuple[Card, list[Event]]:
        done = execute(
            intake(source, runtime), runtime, [ConsoleSink(raw=False)], budget, mode=mode
        )
        lines = (done.folder / "events.jsonl").read_text(encoding="utf-8").splitlines()
        return done.result.card, [Event.model_validate_json(line) for line in lines if line.strip()]

    def key_rows() -> list[str]:
        pool = KeyPool(
            runtime.settings.serpapi_keys,
            runtime.settings.key_reserve,
            account_lookup(runtime.http),
        )
        stats = runtime.ledger.stats()
        rows = [f"key {k.fingerprint}: {k.left} searches left" for k in pool.status()]
        return [
            *rows,
            f"cache hit rate {stats.hit_rate:.0%} · live latency p50 {stats.live_p50_ms} ms",
        ]

    run(Session(live, replay_home(), key_rows), console)


# --- event sinks ---


class ConsoleSink:
    def __init__(self, *, raw: bool) -> None:
        self._raw = raw

    def write(self, event: Event) -> None:
        if self._raw:
            sys.stdout.write(event.model_dump_json() + "\n")
            return
        line = pretty(event)
        if line:
            console.print(line)


def pretty(event: Event) -> str:
    d = event.data
    if event.type == "serp":
        return f"  [cyan]search[/] {d['engine']} · {d['credits']} cr · {d['source']} · {d['latency_ms']} ms"
    if event.type == "agent":
        why = escape(safe(str(d["why"])))[:110]
        warn = f" [red]flagged {escape(str(d['flagged']))}[/]" if d["flagged"] else ""
        terms = escape(safe(str(d["terms"])))
        return f'  [green]agent[/] {d["tool"]} "{terms}" · {d["hits"]} hits · {d["credits"]} cr · {why}{warn}'
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
