# the analyst: answers a person's question about a finished card, citing card lines and, when the card
# can't answer, a few bounded follow-up searches; code checks every citation and word before it is shown
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import BaseModel, Field
from pydantic_ai import Tool
from pydantic_ai.usage import UsageLimits

from quaoar.agent.tools import Toolbox
from quaoar.analyst.evidence import (
    FLAG_WORDS,
    NONE_FLAGGED,
    TOPICS,
    evidence_text,
    pick_lines,
    words,
)
from quaoar.analyst.prompts import ANALYST_PROMPT_VERSION, ANALYST_SYSTEM, analyst_brief
from quaoar.checks.base import SearchPort, safe
from quaoar.checks.book import EvidenceBook, ToolCall
from quaoar.domain.claims import plain
from quaoar.domain.ids import canonical_json, sha256_hex
from quaoar.events import Emitter
from quaoar.guard.advice import ADVICE_REPLY, advice_request
from quaoar.guard.injection import scan_injection
from quaoar.guard.pii import mask_pii
from quaoar.guard.wording import banned_terms
from quaoar.llm.client import LlmClient, LlmError
from quaoar.primer import VERDICT, answer
from quaoar.scoring.card import MARKS, Card

FOLLOW_UP_TOOLS = ("search_registry", "search_maps", "search_legal", "search_news")
CITE = re.compile(r"^[LS]\d{1,3}$")
UNKNOWN = re.compile(
    r"\b(?:doesn't|does not|don't|do not|can't|cannot|couldn't|not)\b.{0,40}\b(?:show|say|cover|find|answer|know)",
    re.I,
)
VERDICT_WORDS = re.compile(r"\byou should\b|\bworth (?:applying|it)\b|\bsafe to\b", re.I)
REFUSED = "That reads like an instruction rather than a question; Quaoar only answers questions about the card."
MAX_TEXT = 900
MAX_CITES = 6


class Answer(BaseModel):
    text: str = Field(
        max_length=MAX_TEXT, description="the answer, at most 120 words, plain language"
    )
    cites: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="ids used: L<n> for card lines, S<n> for follow-up results",
    )


class Trace(BaseModel):
    calls: list[ToolCall]
    answer: Answer | None


@dataclass(frozen=True, slots=True)
class Cited:
    ref: str
    label: str
    url: str = ""
    search_id: str = ""


@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    cites: tuple[Cited, ...]
    mode: str  # agent, evidence or fixed
    searches: int = 0
    credits: int = 0


@dataclass(frozen=True, slots=True)
class AskBudget:
    max_searches: int = 3
    max_credits: int = 3
    # reading lines is free but each read is a model request
    max_requests: int = 10


class Analyst:
    def __init__(
        self,
        llm: LlmClient | None,
        search: SearchPort | None,
        emit: Emitter | None = None,
        budget: AskBudget | None = None,
    ) -> None:
        self._llm, self._search, self._emit = llm, search, emit
        self._budget = budget or AskBudget()

    def ask(self, card: Card, question: str, parent: str | None = None) -> Reply:
        asked = " ".join(safe(question).split())[:400]
        if advice_request(asked) is not None:
            return Reply(ADVICE_REPLY, (), "fixed")
        if scan_injection(asked):
            return Reply(REFUSED, (), "fixed")
        # "is it safe / worth it" gets the same plain no-verdict reply everywhere
        if answer(asked) == VERDICT:
            return Reply(VERDICT, (), "fixed")
        # "why was this flagged" on a card where nothing failed to match has one exact answer
        if card.inconsistent == 0 and words(asked) & FLAG_WORDS:
            return Reply(NONE_FLAGGED, (), "evidence")
        if self._llm is None or self._search is None:
            return from_evidence(card, asked)
        return self._agent(card, asked, self._llm, self._search, parent)

    def _agent(
        self, card: Card, asked: str, llm: LlmClient, search: SearchPort, parent: str | None
    ) -> Reply:
        book = EvidenceBook()
        toolbox = Toolbox(
            search, book, self._emit, parent,
            max_credits=self._budget.max_credits, max_searches=self._budget.max_searches,
            running_numbers=True,
        )  # fmt: skip
        key = sha256_hex(
            canonical_json(
                {
                    "task": "analyst",
                    "prompt": ANALYST_PROMPT_VERSION,
                    "card": sha256_hex(card.model_dump_json()),
                    "question": asked.casefold(),
                }
            )
        )
        # a question already answered for this card is replayed from its trace, with no model call
        recorded = llm.recall(key)
        if recorded is not None:
            trace = Trace.model_validate_json(recorded)
            for call in trace.calls:
                toolbox.dispatch(call)
            return settle(trace.answer, card, book) or from_evidence(card, asked)

        tools = [line_reader(card), *toolbox.tools(FOLLOW_UP_TOOLS)]
        related = [pick.number for pick in pick_lines(card, asked)]
        brief = analyst_brief(card, asked, self._budget.max_searches, related)
        limits = UsageLimits(request_limit=self._budget.max_requests)
        try:
            run = llm.run_agent_or_text(
                "analyst", Answer, ANALYST_SYSTEM, brief, tools, limits, parent
            )
        except LlmError:
            return from_evidence(card, asked)
        answer = run.output if not isinstance(run.output, str) else from_prose(run.output)
        # an empty run is not recorded, so asking again gives the model another chance
        if answer is not None:
            trace = Trace(calls=book.calls, answer=answer)
            llm.remember(
                key, "analyst", trace.model_dump_json().encode(), run.key_fp,
                run.input_tokens, run.output_tokens, run.latency_ns,
            )  # fmt: skip
        return settle(answer, card, book) or from_evidence(card, asked)


PROSE_CITE = re.compile(r"\b([LS]\d{1,3})\b")
CITE_MARKS = re.compile(r"\s*[\[(](?:\s*[LS]\d{1,3}\s*,?)+[\])]")


SENTENCE = re.compile(r"(?<=[.!?])\s+")
SUPPORTED = 0.6
MONTHS = {m: m[:3] for m in ("january", "february", "march", "april", "june", "july", "august",
          "september", "october", "november", "december")}  # fmt: skip


def terms(text: str) -> set[str]:
    return {MONTHS.get(w, w) for w in words(text)}


def attribute(text: str, card: Card) -> list[str]:
    # an answer that cites nothing can still be traced: most of each sentence must come from one line,
    # counting the plain words for that line's check ("lead manager" for the banker check)
    refs: list[str] = []
    for sentence in filter(None, (part.strip() for part in SENTENCE.split(text))):
        said = terms(sentence)
        if not said:
            continue
        support = [
            (len(said & (terms(s.text) | set(TOPICS.get(s.check, ())))) / len(said), n)
            for n, s in enumerate(card.signals, start=1)
        ]
        share, best = max(support, key=lambda pair: (pair[0], -pair[1]))
        if share < SUPPORTED:
            return []
        refs.append(f"L{best}")
    return refs


def from_prose(text: str) -> Answer:
    # a prose answer keeps its inline ids as citations; the same checks then apply
    return Answer(text=text[:MAX_TEXT], cites=PROSE_CITE.findall(text)[:8])


def line_reader(card: Card) -> Tool:
    def read_line(number: int) -> str:
        if not 1 <= number <= len(card.signals):
            return f"<line>no line {number}; the card has lines 1 to {len(card.signals)}</line>"
        s = card.signals[number - 1]
        sources = (
            "\n".join(
                f"- {host(e.url)} | {safe(e.title)[:90]}"
                f"{f' | {e.published}' if e.published else ''} | search {e.search_id or '-'}"
                f" | {safe(e.snippet)[:200]}"
                for e in s.evidence[:3]
            )
            or "- (no source: nothing was found)"
        )
        observed = f"\nobserved: {s.observed}" if s.observed else ""
        return (
            f"<line n={number}>\n[{MARKS[s.status]}] rule {s.rule}, check {s.check}"
            f"{f', prospectus page {s.page}' if s.page else ''}\n{s.text}{observed}\nsources:\n{sources}\n</line>"
        )

    return Tool(
        read_line,
        name="read_line",
        description="Read one card line in full: status, rule, prospectus page and its sources. Free.",
    )


def settle(answer: Answer | None, card: Card, book: EvidenceBook) -> Reply | None:
    # the model's answer is only shown if every citation exists and every word passes the guards
    if answer is None:
        return None
    text = CITE_MARKS.sub("", mask_pii(plain(answer.text)).text).strip()[:MAX_TEXT]
    if not text or banned_terms(text) or VERDICT_WORDS.search(text):
        return None
    named = [*answer.cites, *mentioned_lines(text)]
    cites = cited(named, card, book) or cited(attribute(text, card), card, book)
    if not cites and not UNKNOWN.search(text):
        return None
    if not numbers_grounded(text, sources_text(cites, card, book)):
        return None
    return Reply(text, cites, "agent", searches=book.searches, credits=book.credits)


def cited(refs: list[str], card: Card, book: EvidenceBook) -> tuple[Cited, ...]:
    out: list[Cited] = []
    for raw in refs:
        ref = raw.strip().upper()
        if not CITE.match(ref) or ref in {c.ref for c in out}:
            continue
        number = int(ref[1:])
        if ref[0] == "L" and 1 <= number <= len(card.signals):
            proof = card.signals[number - 1].evidence[:1]
            url, sid = (proof[0].url, proof[0].search_id or "") if proof else ("", "")
            out.append(Cited(ref, f"line {number}", url, sid))
        elif ref[0] == "S" and 1 <= number <= len(book.hits):
            hit = book.hits[number - 1]
            out.append(
                Cited(
                    ref,
                    f"search result {number}",
                    str(hit.item.get("link", "")),
                    hit.result.search_id or "",
                )
            )
    return tuple(out[:MAX_CITES])


NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_of(text: str) -> set[float]:
    found: set[float] = set()
    for raw in NUMBER.findall(text):
        try:
            found.add(float(raw.replace(",", "")))
        except ValueError:
            continue
    return found


LINE_PHRASE = re.compile(r"\blines?\s+\d+(?:\s*(?:,|and|&)\s*\d+)*", re.I)


def mentioned_lines(text: str) -> list[str]:
    # "line 6 says" and "lines 1 and 3" are citations written in prose
    return [f"L{n}" for phrase in LINE_PHRASE.findall(text) for n in re.findall(r"\d+", phrase)]


def sources_text(cites: tuple[Cited, ...], card: Card, book: EvidenceBook) -> str:
    # the card's context notes are part of what any answer may quote
    parts: list[str] = [c.text for c in card.context]
    for cite in cites:
        number = int(cite.ref[1:])
        if cite.ref[0] == "L":
            signal = card.signals[number - 1]
            parts += [
                signal.text,
                signal.observed,
                *(f"{e.title} {e.snippet}" for e in signal.evidence),
            ]
        else:
            item = book.hits[number - 1].item
            parts += [str(item.get(k, "")) for k in ("title", "snippet", "address", "date")]
    return " ".join(parts)


def numbers_grounded(text: str, sources: str) -> bool:
    # every number in an answer must be one its sources state; line numbers are allowed
    allowed = numbers_of(sources) | {float(n) for n in range(0, 11)}
    return numbers_of(text) <= allowed


def from_evidence(card: Card, question: str) -> Reply:
    text, numbers = evidence_text(card, question)
    cites = cited([f"L{n}" for n in numbers], card, EvidenceBook())
    return Reply(text, cites, "evidence")


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")
