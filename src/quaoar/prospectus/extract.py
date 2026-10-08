# claims from located sections: the llm proposes, grounding keeps only what is on the page
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
from quaoar.prospectus.pdf import Page
from quaoar.prospectus.sections import SectionMap

CHUNK_BYTES = 20 * 1024
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
    calls = 0

    for task, (output, names) in TASKS.items():
        kept: list[Grounded] = []
        dropped[task] = 0
        for name in names:
            section = sections.sections.get(name)
            if section is None:
                continue
            for chunk in chunks(safe, section.start, section.end):
                warn_injection(chunk, task, emit, parent)
                result = source.extract(task, output, chunk, parent)
                calls += 1
                for claim in items_of(result):
                    if is_grounded(claim, safe.get(claim.page, "")):
                        kept.append(claim)
                    else:
                        dropped[task] += 1
        claims[task] = dedupe(kept)
    return Extraction(claims, dropped, calls)


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
    if not page or norm(claim.span) not in page:
        return False

    # every value the claim states must also be printed on that page
    values = claim.model_dump(exclude=set(GROUNDING_SKIP))
    return all(norm(str(v)) in page for v in values.values() if isinstance(v, str) and v.strip())


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
