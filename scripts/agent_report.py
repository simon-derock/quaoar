# what did the investigator achieve? gaps closed against searches and tokens, read from stored traces
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from quaoar.serp.ledger import BlobStore


def main(home: Path) -> None:
    db = sqlite3.connect(home / "ledger.sqlite3")
    blobs = BlobStore(home / "blobs")
    rows = db.execute(
        "SELECT task, body_sha256, input_tokens, output_tokens, latency_ns FROM llm_calls WHERE task LIKE 'agent:%'"
    ).fetchall()
    closed, open_ = Counter(), Counter()
    searches = tokens = 0
    for task, sha, tin, tout, _ in rows:
        trace = json.loads(blobs.get(sha))
        handoff = trace.get("handoff") or {}
        closed.update(handoff.get("resolved", []))
        open_.update(handoff.get("unresolved", []))
        searches += len(trace["calls"])
        tokens += tin + tout
        sys.stdout.write(
            f"{task:14s} searches {len(trace['calls'])} resolved {handoff.get('resolved', [])} "
            f"unresolved {handoff.get('unresolved', [])} no-handoff {not handoff}\n"
        )
    sys.stdout.write(
        f"\ninvestigations {len(rows)} · searches {searches} · tokens {tokens} · "
        f"gaps closed {dict(closed)} · gaps left {dict(open_)}\n"
    )


if __name__ == "__main__":
    main(Path.home() / ".quaoar")
