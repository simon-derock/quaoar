# the interactive terminal: type `quaoar`, talk to it; slash commands plus a small intent router
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from quaoar.cli import ConsoleSink, pretty, print_card, safe
from quaoar.events import Event
from quaoar.guard.advice import ADVICE_REPLY, advice_request
from quaoar.guard.injection import scan_injection
from quaoar.guard.text import clean_text
from quaoar.primer import answer
from quaoar.prospectus.acquire import IntakeError
from quaoar.replay import ReplayBundleError, load_replay
from quaoar.scoring.card import MARKS, Card
from quaoar.scoring.comment import draft_comment
from quaoar.serp.client import CreditBudgetExceededError
from quaoar.serp.keys import KeysExhaustedError

BANNER = "QUAOAR · check every IPO before you apply"
PDF_IN_TEXT = re.compile(r"(\S+\.pdf|https://\S+)", re.I)
PROOF = re.compile(r"\b(?:proof|evidence|source)\b.*?(\d+)|\bline\s*(\d+)", re.I)
EXAMPLE = re.compile(r"\b(?:example|demo|sample)\b", re.I)
HELP = """\
type a prospectus path or https url to scan it, or use:
  /scan <pdf|url>   scan a prospectus (uses SerpApi credits)
  /replay <name>    watch a recorded case with no keys (see /cases)
  /cases            list recorded cases
  /card             show the last card again
  /proof <n>        show the evidence behind line n of the card
  /trace            show what caused what in the last scan
  /comment          draft a neutral public-comment letter from the lines that didn't match
  /mode agent|fixed choose how evidence gaps are filled
  /budget <n>       credit cap for the next live scan
  /credits          searches left per key and the cache hit rate
  /help  /quit"""


@dataclass(slots=True)
class Session:
    scan: Callable[[str, str, int], tuple[Card, list[Event]]]
    replay_dir: Path
    credits: Callable[[], list[str]]
    mode: str = "agent"
    budget: int = 0
    card: Card | None = None
    events: list[Event] = field(default_factory=list)


def handle(line: str, session: Session, console: Console) -> bool:
    text = clean_text(line).text.strip()
    if not text:
        return True
    if text.startswith("/"):
        return command(text, session, console)
    if scan_injection(text):
        console.print(
            "[yellow]that looks like an instruction aimed at a model; Quaoar only reads prospectuses.[/]"
        )
        return True
    if advice_request(text) is not None:
        console.print(ADVICE_REPLY)
        if session.card is not None:
            print_card(session.card, console)
        else:
            console.print("Give me a prospectus pdf, or try /replay trafiksol.")
        return True
    return intent(text, session, console)


def intent(text: str, session: Session, console: Console) -> bool:
    proof = PROOF.search(text)
    if proof:
        return command(f"/proof {proof.group(1) or proof.group(2)}", session, console)
    source = PDF_IN_TEXT.search(text)
    if source:
        return command(f"/scan {source.group(1)}", session, console)
    reply = answer(text)
    case = recorded_case(text, session)
    if reply:
        console.print(escape(reply))
    if case:
        return command(f"/replay {case}", session, console)
    if not reply:
        console.print(
            "I can explain IPOs, scan a prospectus pdf, or replay a recorded case. "
            "Try: what is an SME IPO, or /replay trafiksol, or /help."
        )
    return True


def recorded_case(text: str, session: Session) -> str | None:
    # a case named in plain words ("show me the aelea one") or any "example" request replays it
    lowered = text.lower()
    names = sorted(p.name for p in session.replay_dir.glob("*") if p.is_dir())
    for name in names:
        if name.replace("-", " ") in lowered or name in lowered:
            return name
    return "trafiksol" if EXAMPLE.search(text) and "trafiksol" in names else None


def command(text: str, session: Session, console: Console) -> bool:
    name, _, arg = text.partition(" ")
    arg = arg.strip()
    if name in {"/quit", "/exit", "/q"}:
        return False
    handlers: dict[str, Callable[[], None]] = {
        "/help": lambda: console.print(HELP),
        "/cases": lambda: cases(session, console),
        "/replay": lambda: replay(arg, session, console),
        "/scan": lambda: live_scan(arg, session, console),
        "/card": lambda: show_card(session, console),
        "/proof": lambda: proof(arg, session, console),
        "/trace": lambda: trace(session, console),
        "/comment": lambda: letter(session, console),
        "/mode": lambda: set_mode(arg, session, console),
        "/budget": lambda: set_budget(arg, session, console),
        "/credits": lambda: credits_view(session, console),
    }
    action = handlers.get(name)
    if action is None:
        console.print(f"unknown command {escape(name)}; /help lists them")
        return True
    try:
        action()
    except KeyboardInterrupt:
        # Ctrl-C stops the step that is running, not the whole session
        console.print("[yellow]cancelled; partial results are kept in the ledger[/]")
    return True


def credits_view(session: Session, console: Console) -> None:
    for row in session.credits():
        console.print(escape(row))


def cases(session: Session, console: Console) -> None:
    names = sorted(p.name for p in session.replay_dir.glob("*") if p.is_dir())
    console.print("recorded cases: " + (", ".join(names) if names else "none"))


def replay(name: str, session: Session, console: Console) -> None:
    if not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        console.print("give the case name, for example /replay trafiksol")
        return
    try:
        events, card = load_replay(session.replay_dir / name)
    except ReplayBundleError:
        console.print(f"no recorded case called {escape(name)}; see /cases")
        return
    sink = ConsoleSink(raw=False)
    for event in events:
        sink.write(event)
    session.card, session.events = card, events
    print_card(card, console)


def live_scan(source: str, session: Session, console: Console) -> None:
    if not source:
        console.print("usage: /scan <pdf path or https url>")
        return
    try:
        card, events = session.scan(source, session.mode, session.budget)
    except (IntakeError, KeysExhaustedError, CreditBudgetExceededError) as exc:
        console.print(f"[yellow]stopped:[/yellow] {escape(str(exc))}")
        return
    session.card, session.events = card, events
    print_card(card, console)


def letter(session: Session, console: Console) -> None:
    if session.card is None:
        console.print("no card yet: scan something or /replay a case")
        return
    text = draft_comment(session.card)
    console.print(escape(text) if text else "nothing to comment on: no line failed to match")


def show_card(session: Session, console: Console) -> None:
    if session.card is None:
        console.print("no card yet: scan something or /replay a case")
        return
    print_card(session.card, console)


def proof(arg: str, session: Session, console: Console) -> None:
    if session.card is None:
        console.print("no card yet: scan something or /replay a case")
        return
    if not arg.isdigit() or not 1 <= int(arg) <= len(session.card.signals):
        console.print(f"give a line number from 1 to {len(session.card.signals)}")
        return
    signal = session.card.signals[int(arg) - 1]
    console.print(f"[bold]{MARKS[signal.status]}[/] {escape(safe(signal.text))}")
    if not signal.evidence:
        console.print("  no source: nothing was found to show")
    for item in signal.evidence:
        when = f" · {item.published}" if item.published else ""
        console.print(f"  {escape(item.title)}{when}")
        console.print(f"  {escape(item.url)}")
        console.print(f"  via {item.engine}, SerpApi search id {escape(item.search_id or '-')}")
        if item.snippet:
            console.print(f"  “{escape(item.snippet)}”")


def trace(session: Session, console: Console) -> None:
    if not session.events:
        console.print("no scan yet")
        return
    depth: dict[str, int] = {}
    for event in session.events:
        level = depth.get(event.parent, -1) + 1 if event.parent else 0
        depth[event.id] = level
        line = pretty(event)
        if line:
            console.print("  " * level + line.strip())


def set_mode(arg: str, session: Session, console: Console) -> None:
    if arg not in {"agent", "fixed"}:
        console.print("mode is agent or fixed")
        return
    session.mode = arg
    console.print(f"mode: {arg}")


def set_budget(arg: str, session: Session, console: Console) -> None:
    if not arg.isdigit() or not 1 <= int(arg) <= 100:
        console.print("budget is a number of credits from 1 to 100")
        return
    session.budget = int(arg)
    console.print(f"credit cap for the next scan: {arg}")


def run(session: Session, console: Console, read: Callable[[str], str] = input) -> None:
    console.print(f"[bold]{BANNER}[/]")
    console.print(f"mode {session.mode} · type /help")
    while True:
        try:
            line = read("\u203a ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        if not handle(line, session, console):
            return
