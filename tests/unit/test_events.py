# spec: SPEC-EVT-01, SPEC-RT-04, SPEC-RT-05
import json
from pathlib import Path

import pytest

from quaoar.events import Emitter, EventTooLargeError, JournalSink, MemorySink
from tests.fakes import FixedClock


def test_ids_are_sequential_and_parents_rebuild_the_chain() -> None:
    sink = MemorySink()
    emit = Emitter("scan1", sink, FixedClock())
    check = emit("stage", {"name": "vendor"})
    tool = emit("serp", {"engine": "google"}, parent=check)
    emit("signal", {"status": "UNVERIFIED"}, parent=tool)

    assert [e.id for e in sink.events] == ["scan1-000001", "scan1-000002", "scan1-000003"]
    chain = chain_to_root(sink, "scan1-000003")
    assert chain == ["signal", "serp", "stage"]


def test_events_carry_version_scan_and_monotonic_time() -> None:
    sink = MemorySink()
    emit = Emitter("s", sink, FixedClock())
    emit("stage", {})
    emit("done", {})
    first, second = sink.events
    assert (first.v, first.scan) == (1, "s")
    assert second.t_ns > first.t_ns


def test_journal_appends_one_json_line_per_event_and_flushes(tmp_path: Path) -> None:
    path = tmp_path / "events" / "s.jsonl"
    emit = Emitter("s", JournalSink(path), FixedClock())
    emit("stage", {"name": "sections"})
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["type"] == "stage"
    emit("done", {})
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_oversized_event_is_refused_so_big_data_goes_to_blobs() -> None:
    emit = Emitter("s", MemorySink(), FixedClock())
    with pytest.raises(EventTooLargeError):
        emit("serp", {"body": "x" * 5_000})


def test_scrub_runs_over_every_string_in_the_payload() -> None:
    sink = MemorySink()
    emit = Emitter("s", sink, FixedClock(), scrub=lambda text: text.replace("secret", "[redacted]"))
    emit("serp", {"url": "a?secret", "nested": {"items": ["secret", 3]}})
    data = sink.events[0].data
    assert data == {"url": "a?[redacted]", "nested": {"items": ["[redacted]", 3]}}


def chain_to_root(sink: MemorySink, event_id: str) -> list[str]:
    by_id = {e.id: e for e in sink.events}
    types: list[str] = []
    current: str | None = event_id
    while current is not None:
        event = by_id[current]
        types.append(event.type)
        current = event.parent
    return types


def test_a_fresh_journal_replaces_the_previous_run(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    Emitter("s", JournalSink(path), FixedClock())("stage", {"name": "old"})
    Emitter("s", JournalSink(path, fresh=True), FixedClock())("stage", {"name": "new"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["data"]["name"] == "new"
