# turns the saved cards of the positive and the controls into the results table in the audit doc
import json
import sqlite3
import sys
from pathlib import Path

from quaoar.backtest.metrics import CaseResult, describe, from_card, summarize
from quaoar.scoring.card import Card

CASES = (
    ("Trafiksol ITS Technologies (final prospectus)", "positive", "c9153f936c7c"),
    ("Trafiksol ITS Technologies (red herring)", "positive", "25ef54ec6314"),
    ("Aelea Commodities", "control", "fb6a3e3b4d5b"),
    ("Indian Emulsifier", "control", "364487443e9c"),
    ("TBI Corn", "control", "6ab4ed705448"),
)


def main(home: Path, doc: Path, heading: str, slug: str) -> None:
    db = sqlite3.connect(home / "ledger.sqlite3")
    results: list[CaseResult] = []
    rows, details = [], []
    for name, role, prefix in CASES:
        folder = find_scan(home, prefix)
        if folder is None:
            rows.append(f"| {name} | {role} | not scanned | | |")
            continue
        card = Card.model_validate_json((folder / "card.json").read_text(encoding="utf-8"))
        paid = db.execute(
            "SELECT COALESCE(SUM(credits),0) FROM uses WHERE scan=? AND cached=0", (card.scan_id,)
        ).fetchone()[0]
        case = from_card(name, role, card, int(paid))
        results.append(case)
        rows.append(
            f"| {name} | {role} | {'yes' if case.flagged else 'no'} | {case.consistent} / {case.inconsistent} / {case.unverified} | {case.credits} |"
        )
        details += [
            f"- **{name}**: {s.rule} - {s.text}"
            for s in card.signals
            if s.status.value == "inconsistent"
        ]
    summary = summarize(results)
    lines = [
        f"### {heading}",
        "",
        "| Issuer | Role | Flagged | Checks out / doesn't match / couldn't find | Searches paid in this run |",
        "|---|---|---|---|---:|",
        *rows,
        "",
        describe(summary.positives, "Positives")
        + ". "
        + describe(summary.controls, "Controls")
        + ". With this few cases the intervals are wide.",
        "",
        "Lines that did not match:" if details else "No case produced a line that did not match.",
        *details,
    ]
    write_block(doc, slug, "\n".join(lines))
    sys.stdout.write("\n".join(lines) + "\n")


def write_block(doc: Path, slug: str, block: str) -> None:
    # one block per run, so run 1 is never overwritten by run 2
    start, end = f"<!-- results:{slug}:start -->", f"<!-- results:{slug}:end -->"
    text = doc.read_text(encoding="utf-8")
    wrapped = f"{start}\n{block}\n{end}"
    if start in text:
        head, rest = text.split(start, 1)
        text = head + wrapped + rest.split(end, 1)[1]
    else:
        text = text.rstrip("\n") + "\n\n" + wrapped + "\n"
    doc.write_text(text, encoding="utf-8")


def find_scan(home: Path, prefix: str) -> Path | None:
    for events in sorted((home / "scans").glob("*/events.jsonl")):
        first = events.read_text(encoding="utf-8").splitlines()[:1]
        if (
            first
            and prefix in json.loads(first[0])["data"].get("sha256", "")
            and (events.parent / "card.json").is_file()
        ):
            return events.parent
    return None


if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else "Results"
    key = sys.argv[2] if len(sys.argv) > 2 else "run"
    main(Path.home() / ".quaoar", Path("docs/benchmark-audits/controls-2026-10-09.md"), title, key)
