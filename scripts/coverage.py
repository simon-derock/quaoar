# can Quaoar read real prospectuses? fetch, read pages, locate sections, no search credit and no model call
# usage: uv run python scripts/coverage.py SAMPLE.txt DOWNLOAD_DIR OUT.json [EARLIER.json]
# with an earlier run's json, files already downloaded are read from disk, not fetched again
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from quaoar.prospectus.acquire import IntakeError, Prospectus, from_path, from_url
from quaoar.prospectus.meta import prospectus_date, require_prospectus
from quaoar.prospectus.pdf import PdfParseError, read_pages
from quaoar.prospectus.sections import TARGETS, locate_sections
from quaoar.scan import issuer_name

PAUSE_S = 1.5
READABLE = 0.9
SME_PAGES = 12
# the listing statement of an SME issue names the SME or EMERGE platform; a mainboard one names BSE and NSE
SME_LISTING = re.compile(r"SME PLATFORM|EMERGE PLATFORM|BSE SME|NSE EMERGE|SME EXCHANGE")


@dataclass(slots=True)
class Row:
    url: str
    sha256: str = ""
    size_mb: float = 0.0
    fetched: bool = False
    error: str = ""
    pages: int = 0
    text_share: float = 0.0
    sme: bool = False
    recognised: bool = False
    found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    issuer: str = ""
    dated: str = ""


def check(url: str, folder: Path, http: httpx.Client, earlier: dict[str, str]) -> Row:
    row = Row(url)
    try:
        got = fetch(url, folder, http, earlier)
    except IntakeError as exc:
        row.error = str(exc)
        return row
    row.fetched, row.sha256, row.size_mb = True, got.sha256, round(got.size / 1e6, 1)
    try:
        pages = read_pages(got.path)
    except PdfParseError as exc:
        row.error = f"parse: {exc}"
        return row
    row.pages = len(pages)
    row.text_share = round(sum(not p.needs_ocr for p in pages) / max(1, len(pages)), 2)
    front = " ".join(" ".join(p.text.split()) for p in pages[:SME_PAGES]).upper()
    row.sme = SME_LISTING.search(front) is not None
    try:
        require_prospectus(pages)
        row.recognised = True
    except IntakeError as exc:
        row.error = str(exc)
    sections = locate_sections(pages)
    row.found = sorted(sections.sections)
    row.missing = sorted(set(TARGETS) - set(sections.sections))
    row.issuer = issuer_name(pages)
    when = prospectus_date(pages)
    row.dated = when.isoformat() if when else ""
    return row


def fetch(url: str, folder: Path, http: httpx.Client, earlier: dict[str, str]) -> Prospectus:
    kept = folder / f"{earlier.get(url, '-')}.pdf"
    if kept.is_file():
        return from_path(kept)
    got = from_url(url, folder, http)
    time.sleep(PAUSE_S)
    return got


def main(sample: Path, folder: Path, out: Path, before: Path | None) -> None:
    urls = [u.strip() for u in sample.read_text().splitlines() if u.strip()]
    earlier = {r["url"]: r["sha256"] for r in json.loads(before.read_text())} if before else {}
    with httpx.Client() as http:
        rows = [check(url, folder, http, earlier) for url in urls]
    out.write_text(json.dumps([asdict(r) for r in rows], indent=1))
    report(rows)


def report(rows: list[Row]) -> None:
    write = sys.stdout.write
    write(
        "| # | file | MB | pages | text | SME | recognised | sections | issuer | dated | note |\n"
    )
    write("|---|---|---|---|---|---|---|---|---|---|---|\n")
    for i, r in enumerate(rows, 1):
        name = r.url.rsplit("/", 1)[-1]
        write(
            f"| {i} | {name} | {r.size_mb} | {r.pages} | {r.text_share} | {'y' if r.sme else 'n'} "
            f"| {'y' if r.recognised else 'n'} | {len(r.found)}/7 | {r.issuer} | {r.dated or '-'} "
            f"| {r.error or ''}{' missing ' + ','.join(r.missing) if r.missing and r.fetched else ''} |\n"
        )


if __name__ == "__main__":
    main(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]) if len(sys.argv) > 4 else None,
    )
