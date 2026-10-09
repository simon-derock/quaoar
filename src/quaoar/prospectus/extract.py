# claims from located sections: the llm proposes, grounding keeps only what is on the page
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from quaoar.domain.claims import (
    DisclosedCases,
    Grounded,
    GroupCompanies,
    LeadManagers,
    PastIssues,
    Places,
    Promoters,
    Quotes,
)
from quaoar.events import Emitter
from quaoar.guard.injection import scan_injection
from quaoar.guard.pii import mask_pii
from quaoar.guard.text import clean_text
from quaoar.llm.client import LlmError
from quaoar.prospectus.pdf import Page
from quaoar.prospectus.sections import SectionMap

CHUNK_BYTES = 20 * 1024
SPAN_CHARS = 300
# a section the model refuses is asked again in halves, down to this size
MIN_SPLIT_BYTES = 3000
MAX_SPLITS = 2
PAGE_MARKER = re.compile(r"\[\[page \d+\]\]")
# role words the model sometimes returns where a name should be
GENERIC_NAMES = frozenset(
    {"book running lead manager", "book running lead managers", "lead manager", "lead managers",
     "brlm", "registrar", "registrar to the issue", "promoter", "promoters", "group company"}
)  # fmt: skip
SPAN_BEFORE = 60
GROUNDING_SKIP = frozenset({"page", "span", "role"})
TASKS: dict[str, tuple[type[BaseModel], tuple[str, ...]]] = {
    "quotes": (Quotes, ("objects",)),
    "lead_managers": (LeadManagers, ("general_information",)),
    "past_issues": (PastIssues, ("regulatory",)),
    "cases": (DisclosedCases, ("litigation",)),
    "places": (Places, ("general_information",)),
    "promoters": (Promoters, ("promoters",)),
    "group_companies": (GroupCompanies, ("group_companies",)),
}


class ClaimSource(Protocol):
    def extract[T: BaseModel](
        self, task: str, output: type[T], text: str, parent: str | None = None
    ) -> T: ...


@dataclass(frozen=True, slots=True)
class Extraction:
    claims: dict[str, list[Grounded]]
    ungrounded: dict[str, int]
    failed: dict[str, int]
    calls: int


def extract_claims(
    pages: list[Page],
    sections: SectionMap,
    source: ClaimSource,
    emit: Emitter | None = None,
    parent: str | None = None,
) -> Extraction:
    # personal identifiers are masked before any text leaves the machine
    safe = {p.number: safe_text(p.text) for p in pages}
    claims: dict[str, list[Grounded]] = {}
    dropped: dict[str, int] = {}
    failed: dict[str, int] = {}
    calls = 0

    for task, (output, names) in TASKS.items():
        kept: list[Grounded] = []
        dropped[task] = failed[task] = 0
        for name in names:
            section = sections.sections.get(name)
            if section is None:
                continue
            for chunk in chunks(safe, section.start, section.end):
                warn_injection(chunk, task, emit, parent)
                # one unreadable chunk becomes "couldn't read", never a crashed scan
                results, made, bad = ask(source, task, output, chunk, parent)
                calls += made
                failed[task] += bad
                for claim in (c for result in results for c in items_of(result)):
                    page_text = safe.get(claim.page, "")
                    if is_generic(claim):
                        dropped[task] += 1
                    elif is_grounded(claim, page_text):
                        kept.append(with_page_span(claim, page_text))
                    else:
                        dropped[task] += 1
        claims[task] = dedupe(kept)
    return Extraction(claims, dropped, failed, calls)


def ask(
    source: ClaimSource,
    task: str,
    output: type[BaseModel],
    text: str,
    parent: str | None,
    depth: int = 0,
) -> tuple[list[BaseModel], int, int]:
    # returns (answers, model calls made, pieces that could not be read)
    try:
        return [source.extract(task, output, text, parent)], 1, 0
    except LlmError:
        parts = halve(text) if depth < MAX_SPLITS and len(text.encode()) > MIN_SPLIT_BYTES else []
        if not parts:
            return [], 1, 1
    answers: list[BaseModel] = []
    calls = bad = 0
    for part in parts:
        got, made, missed = ask(source, task, output, part, parent, depth + 1)
        answers += got
        calls += made
        bad += missed
    return answers, calls + 1, bad


def halve(text: str) -> list[str]:
    # cut near the middle at a line break; the second half keeps the page marker it was under
    middle = len(text) // 2
    low = middle // 2
    cut = next(
        (c for c in (text.rfind("\n", low, middle + 1), text.rfind(" ", low, middle + 1)) if c > 0),
        middle,
    )
    head, tail = text[:cut], text[cut:].lstrip("\n")
    if not head.strip() or not tail.strip():
        return []
    markers = PAGE_MARKER.findall(head)
    if markers and not tail.startswith("[[page"):
        tail = f"{markers[-1]}\n{tail}"
    return [head, tail]


def safe_text(text: str) -> str:
    return mask_pii(clean_text(text).text).text


def chunks(pages: dict[int, str], start: int, end: int) -> list[str]:
    out: list[str] = []
    current = ""
    for number in range(start, end + 1):
        for block in page_blocks(number, pages.get(number, "")):
            if current and len((current + block).encode()) > CHUNK_BYTES:
                out.append(current)
                current = ""
            current += block
    if current:
        out.append(current)
    return out


def page_blocks(number: int, text: str) -> list[str]:
    # an oversized page is cut into pieces that each keep the page marker
    marker = f"[[page {number}]]\n"
    room = CHUNK_BYTES - len(marker.encode()) - 64
    pieces = [text[i : i + room] for i in range(0, max(len(text), 1), room)] or [""]
    return [f"{marker}{piece}\n" for piece in pieces]


def warn_injection(chunk: str, task: str, emit: Emitter | None, parent: str | None) -> None:
    hits = scan_injection(chunk)
    if hits and emit is not None:
        emit(
            "guard",
            {"guard": "G2", "source": f"prospectus:{task}", "rules": [h.rule for h in hits]},
            parent,
        )


def items_of(result: BaseModel) -> Sequence[Grounded]:
    items = getattr(result, "items", [])
    return [item for item in items if isinstance(item, Grounded)]


def is_grounded(claim: Grounded, page_text: str) -> bool:
    page = norm(page_text)
    values = claim_values(claim)
    # every value the claim states must be printed on the page it cites
    return bool(page) and bool(values) and all(norm(v) in page for v in values)


EXPENSE_ROW = re.compile(
    r"\b(fees?|expenses?|commission|charges|payable|brokerage|total|stamp duty|printing|advertis\w*|"
    r"miscellaneous|contingenc\w*|registrar|underwriting)\b",
    re.I,
)


def is_generic(claim: Grounded) -> bool:
    name = getattr(claim, "name", None)
    if isinstance(name, str) and norm(name) in GENERIC_NAMES:
        return True
    # rows of the issue-expenses table ("Total Estimated Issue Expenses", "Lead Manger Fees ...") are not vendors
    vendor = getattr(claim, "vendor", None)
    return isinstance(vendor, str) and bool(EXPENSE_ROW.search(vendor))


def with_page_span(claim: Grounded, page_text: str) -> Grounded:
    # the quote shown to people is cut from the page by code around the first value
    flat = " ".join(page_text.split())
    anchor = claim_values(claim)[0]
    at = flat.casefold().find(" ".join(anchor.split()).casefold())
    start = max(0, at - SPAN_BEFORE) if at >= 0 else 0
    return claim.model_copy(update={"span": flat[start : start + SPAN_CHARS]})


def claim_values(claim: Grounded) -> list[str]:
    values = claim.model_dump(exclude=set(GROUNDING_SKIP))
    return [v for v in values.values() if isinstance(v, str) and v.strip()]


def dedupe(claims: list[Grounded]) -> list[Grounded]:
    seen: set[tuple[object, ...]] = set()
    out: list[Grounded] = []
    for claim in claims:
        key = (type(claim).__name__, *(
            norm(str(v)) for k, v in sorted(claim.model_dump().items()) if k not in GROUNDING_SKIP
        ))  # fmt: skip
        if key not in seen:
            seen.add(key)
            out.append(claim)
    return out


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    return " ".join(text.split())
