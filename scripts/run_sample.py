# phases B and C of the coverage test: read claims for every located SME prospectus, and run a full
# scan while search credits last; one record per prospectus, written as it finishes
# usage: uv run python scripts/run_sample.py RESULT.json PDF_DIR OUT.json scan
#        uv run python scripts/run_sample.py RESULT.json PDF_DIR OUT.json claims SHARD SHARDS
# one scan worker takes the prospectuses in order while credits last; claim workers share all of them,
# and a model answer already in the ledger is reused, so overlap costs nothing
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from quaoar.clock import SystemClock
from quaoar.events import Emitter, MemorySink
from quaoar.llm.client import LlmClient, LlmError
from quaoar.prospectus.acquire import from_path
from quaoar.prospectus.extract import Extraction, extract_claims
from quaoar.prospectus.pdf import read_pages
from quaoar.prospectus.sections import locate_sections
from quaoar.serp.client import CreditBudgetExceededError, account_lookup
from quaoar.serp.keys import KeysExhaustedError
from quaoar.service import execute, make_runtime

SCAN_CAP = 24
# scanned in an earlier audit, so not scanned again here
EARLIER = ("PR00682", "PR0068D", "PR0067L", "PR0063G")


@dataclass(slots=True)
class Record:
    url: str
    sha256: str
    issuer: str
    kind: str = ""
    status: str = ""
    credits: int = 0
    consistent: int = 0
    inconsistent: int = 0
    unverified: int = 0
    signals: list[dict[str, str]] = field(default_factory=list)
    claims: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, int] = field(default_factory=dict)
    failed: dict[str, int] = field(default_factory=dict)
    calls: int = 0


def take(record: Record, extraction: Extraction) -> None:
    record.claims = {task: len(items) for task, items in extraction.claims.items()}
    record.dropped = dict(extraction.ungrounded)
    record.failed = dict(extraction.failed)
    record.calls = extraction.calls


def claims_only(record: Record, path: Path) -> None:
    runtime = make_runtime()
    clock = SystemClock()
    llm = LlmClient(
        ledger=runtime.ledger,
        clock=clock,
        model_name=runtime.settings.cohere_model,
        keys=runtime.settings.cohere_keys,
        emit=Emitter("coverage", MemorySink(), clock),
    )
    pages = read_pages(path)
    take(record, extract_claims(pages, locate_sections(pages), llm))
    record.kind, record.status = "claims", "read"


def full_scan(record: Record, path: Path) -> None:
    runtime = make_runtime()
    done = execute(from_path(path), runtime, max_credits=SCAN_CAP, mode="fixed")
    card = done.result.card
    take(record, done.result.extraction)
    record.kind, record.status, record.credits = "scan", "card", done.credits
    record.consistent, record.inconsistent, record.unverified = (
        card.consistent,
        card.inconsistent,
        card.unverified,
    )
    record.signals = [
        {"rule": s.rule, "check": s.check, "status": s.status.value, "text": s.text[:200]}
        for s in done.result.signals
    ]


def main(result: Path, folder: Path, out: Path, role: str, shard: int, shards: int) -> None:
    rows = [r for r in json.loads(result.read_text()) if r["sme"] and len(r["found"]) == 7]
    rows.sort(key=lambda r: r["sha256"])
    runtime = make_runtime()
    lookup = account_lookup(runtime.http)
    key = runtime.settings.serpapi_keys[0].get_secret_value()
    if role == "claims":
        rows = rows[shard::shards]
    else:
        rows = [r for r in rows if r["url"].rsplit("/", 1)[-1].removesuffix(".pdf") not in EARLIER]
    records: list[Record] = []
    for row in rows:
        record = Record(row["url"], row["sha256"], row["issuer"])
        path = folder / f"{row['sha256']}.pdf"
        left = lookup(key)
        if role == "scan" and left < SCAN_CAP:
            break
        try:
            if role == "scan":
                full_scan(record, path)
            else:
                claims_only(record, path)
        except (CreditBudgetExceededError, KeysExhaustedError) as exc:
            record.kind, record.status = "scan", f"stopped: {type(exc).__name__}"
            record.credits = left - lookup(key)
        except (LlmError, sqlite3.OperationalError, httpx.HTTPError) as exc:
            record.status = f"error: {type(exc).__name__}: {exc}"[:200]
        records.append(record)
        out.write_text(json.dumps([asdict(r) for r in records], indent=1))
        sys.stderr.write(
            f"{len(records)}/{len(rows)} {record.url[-11:-4]} {record.kind} {record.status}\n"
        )


if __name__ == "__main__":
    main(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        sys.argv[4],
        int(sys.argv[5]) if len(sys.argv) > 5 else 0,
        int(sys.argv[6]) if len(sys.argv) > 6 else 1,
    )
