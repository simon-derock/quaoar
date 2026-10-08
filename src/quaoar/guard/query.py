# G3 query guard: only allowlisted engines and params reach SerpApi, with safe defaults
import re
from collections.abc import Mapping

MAX_VALUE_LENGTH = 512

# engine -> (allowed params, one-of required params, defaults)
ENGINES: dict[str, tuple[frozenset[str], tuple[str, ...], dict[str, str]]] = {
    "google": (
        frozenset({"q", "location", "gl", "hl", "num", "start", "tbs", "safe", "filter"}),
        ("q",),
        {"gl": "in", "hl": "en"},
    ),
    "google_news": (frozenset({"q", "gl", "hl"}), ("q",), {"gl": "in", "hl": "en"}),
    "google_maps": (frozenset({"q", "ll", "type", "hl", "start"}), ("q",), {"hl": "en"}),
    "google_maps_reviews": (
        frozenset({"data_id", "place_id", "hl", "sort_by", "next_page_token"}),
        ("data_id", "place_id"),
        {"hl": "en"},
    ),
    "youtube": (frozenset({"search_query", "gl", "hl", "sp"}), ("search_query",), {"gl": "IN"}),
    "google_trends": (
        frozenset({"q", "geo", "date", "data_type", "hl", "tz"}),
        ("q",),
        {"geo": "IN", "hl": "en"},
    ),
    "google_finance": (frozenset({"q", "hl", "window"}), ("q",), {"hl": "en"}),
    "google_jobs": (frozenset({"q", "location", "gl", "hl"}), ("q",), {"gl": "in", "hl": "en"}),
    "google_patents": (frozenset({"q", "num", "page", "country", "assignee"}), ("q",), {}),
    "google_lens": (frozenset({"url", "hl", "country", "type"}), ("url",), {"hl": "en"}),
}
SITE_ALLOWLIST = frozenset(
    {
        "sebi.gov.in",
        "indiankanoon.org",
        "ibbi.gov.in",
        "nclt.gov.in",
        "instafinancials.com",
        "zaubacorp.com",
        "tofler.in",
        "chittorgarh.com",
    }
)
SITE = re.compile(r"\bsite:([a-z0-9.-]+)", re.I)
SECRETISH = re.compile(r"api_key|apikey|bearer\s", re.I)
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
SAFE_URL = re.compile(r"^https://[a-z0-9.-]+(?::\d{2,5})?/\S{0,1900}$", re.I)


class QueryRejectedError(ValueError):
    def __init__(self, rule: str, detail: str) -> None:
        super().__init__(f"{rule}: {detail}")
        self.rule = rule


def prepare_query(engine: str, params: Mapping[str, object]) -> dict[str, str]:
    if engine not in ENGINES:
        raise QueryRejectedError("engine", engine)
    allowed, required, defaults = ENGINES[engine]

    unknown = sorted(set(params) - allowed)
    if unknown:
        raise QueryRejectedError("param", ", ".join(unknown))
    if not any(params.get(name) for name in required):
        raise QueryRejectedError("required", " or ".join(required))

    values = {name: str(value) for name, value in params.items()}
    for name, value in values.items():
        check_value(name, value)
    check_sites(values)
    return dict(sorted({**defaults, **values}.items()))


def check_value(name: str, value: str) -> None:
    if len(value) > MAX_VALUE_LENGTH:
        raise QueryRejectedError("length", name)
    if CONTROL.search(value):
        raise QueryRejectedError("control", name)
    if SECRETISH.search(value):
        raise QueryRejectedError("secret", name)
    if name == "url" and not SAFE_URL.match(value):
        raise QueryRejectedError("url", "https without credentials only")


def check_sites(values: dict[str, str]) -> None:
    sites = {s.lower() for s in SITE.findall(values.get("q", ""))}
    outside = sorted(sites - SITE_ALLOWLIST)
    if outside:
        raise QueryRejectedError("site", ", ".join(outside))

    # SerpApi issue #4396: site: plus a tbs date filter returns nothing, so dates are filtered locally
    if sites and "tbs" in values:
        raise QueryRejectedError("site_tbs", "filter dates locally instead")
