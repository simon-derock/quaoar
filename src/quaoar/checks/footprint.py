# public footprint of an IPO: dated news (any adverse coverage) and promotion volume on youtube
import re
from dataclasses import dataclass, field
from datetime import date

from quaoar.checks.base import SearchPort, evidence, results
from quaoar.checks.registry import registry_core
from quaoar.domain.dates import parse_date
from quaoar.domain.findings import Evidence
from quaoar.domain.names import normalize_company

ADVERSE = re.compile(
    r"\b(sebi|probe|investigat\w*|complaint|halt\w*|defer\w*|barred|ban(?:s|ned)?|penalt\w*|"
    r"diver\w+|misuse|refund|show[- ]cause|raid\w*|arrest\w*)\b",
    re.I,
)
PROMO = re.compile(r"\b(gmp|apply|ipo review|should you|subscribe|allotment|listing)\b", re.I)


@dataclass(slots=True)
class Article:
    title: str
    when: date | None
    adverse: bool
    evidence: Evidence


@dataclass(slots=True)
class FootprintFindings:
    issuer: str
    articles: list[Article] = field(default_factory=list)
    videos: int = 0
    promo_videos: int = 0


def footprint(issuer: str, search: SearchPort, parent: str | None = None) -> FootprintFindings:
    core = registry_core(issuer)
    key = normalize_company(issuer)
    found = FootprintFindings(issuer)

    news = search.query("google_news", {"q": f'"{core}" IPO'}, parent)
    for item in results(news, "news_results"):
        title = str(item.get("title", ""))
        if key.split()[0] not in normalize_company(title):
            continue
        raw = item.get("date")
        found.articles.append(
            Article(title, parse_date(raw) if isinstance(raw, str) else None, bool(ADVERSE.search(title)), evidence(news, item))
        )  # fmt: skip

    clips = search.query("youtube", {"search_query": f"{core} IPO"}, parent)
    for item in results(clips, "video_results"):
        title = str(item.get("title", ""))
        if key.split()[0] in normalize_company(title):
            found.videos += 1
            found.promo_videos += bool(PROMO.search(title))
    return found
