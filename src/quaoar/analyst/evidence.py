# answers a question from the card alone, with no model: the analyst's floor, used offline, in replays
# and whenever a model answer fails its checks
import re
from dataclasses import dataclass

from quaoar.domain.findings import Signal, Status
from quaoar.scoring.card import MARKS, Card

TOPICS: dict[str, tuple[str, ...]] = {
    "vendor": ("vendor", "quote", "quotation", "supplier", "software", "capital", "paid", "registry", "cin"),
    "site": ("office", "factory", "premises", "address", "maps", "location", "warehouse", "plant", "where"),
    "banker": ("banker", "lead", "manager", "merchant", "brlm", "underwriter"),
    "litigation": ("court", "case", "cases", "litigation", "legal", "dispute", "insolvency", "ibbi"),
    "footprint": ("news", "media", "youtube", "coverage", "hype", "promotion", "video", "videos"),
}  # fmt: skip
FLAG_WORDS = frozenset(
    {"why", "flag", "flagged", "wrong", "problem", "issue", "mismatch", "match", "red",
     "concern", "worry", "bad", "suspicious", "odd", "strange"}
)  # fmt: skip
STOP = frozenset(
    {"the", "and", "for", "this", "that", "with", "what", "does", "did", "was", "are", "is",
     "its", "it's", "about", "there", "any", "how", "who", "which", "from", "have", "has", "ipo",
     "company", "card", "line", "lines", "tell", "show", "me", "please"}
)  # fmt: skip
WORD = re.compile(r"[a-z0-9]+")
LINE_REF = re.compile(r"\bline\s*(\d+)", re.I)
MAX_LINES = 3
NOT_COVERED = (
    "This card doesn't cover that. It checks the vendor, the premises, the lead manager, "
    "court and SEBI matters, and news; ask about one of those, or /proof <n> for a line's source."
)
TOPIC_NAMES = {
    "vendor": "the vendor",
    "site": "the company's premises",
    "banker": "the lead manager",
    "litigation": "court or SEBI matters",
    "footprint": "news coverage",
}
NONE_FLAGGED = (
    "No line on this card fails to match. Lines marked couldn't find are gaps, not findings."
)


@dataclass(frozen=True, slots=True)
class Pick:
    number: int
    signal: Signal


def words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) > 2 and w not in STOP}


def topics_of(asked: set[str]) -> set[str]:
    return {check for check, cues in TOPICS.items() if asked & set(cues)}


def score(signal: Signal, asked: set[str], topics: set[str], *, flag: bool) -> int:
    points = 3 * (signal.check in topics) + len(asked & words(signal.text))
    return points + 3 * (flag and signal.status is Status.INCONSISTENT)


def pick_lines(card: Card, question: str) -> list[Pick]:
    # an explicit "line 4" is answered with that line
    ref = LINE_REF.search(question)
    if ref and 1 <= int(ref.group(1)) <= len(card.signals):
        number = int(ref.group(1))
        return [Pick(number, card.signals[number - 1])]
    asked = words(question)
    topics, flag = topics_of(asked), bool(asked & FLAG_WORDS)
    scored = [
        (score(s, asked, topics, flag=flag), Pick(n, s))
        for n, s in enumerate(card.signals, start=1)
    ]
    ranked = sorted((item for item in scored if item[0] > 0), key=lambda item: -item[0])
    return [pick for _, pick in ranked[:MAX_LINES]]


def missing_topic(card: Card, question: str) -> str | None:
    # asked about something this card has no line on: say so rather than cite loosely related lines
    asked = topics_of(words(question))
    present = {s.check for s in card.signals}
    absent = sorted(asked - present)
    if asked and not asked & present:
        names = " or ".join(TOPIC_NAMES[t] for t in absent)
        return f"This card has no line about {names}: the scan found nothing it could check there."
    return None


def evidence_text(card: Card, question: str) -> tuple[str, list[int]]:
    gap = missing_topic(card, question)
    if gap is not None:
        return gap, []
    picks = pick_lines(card, question)
    if not picks:
        flagged = words(question) & FLAG_WORDS
        return (NONE_FLAGGED if flagged and card.inconsistent == 0 else NOT_COVERED), []
    rows = [f"line {p.number}, {MARKS[p.signal.status]}: {p.signal.text}" for p in picks]
    return "From this card:\n" + "\n".join(rows), [p.number for p in picks]
