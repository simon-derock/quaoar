# spec: SPEC-LGR-01, SPEC-LGR-02, SPEC-LGR-03, SPEC-LGR-04, SPEC-SAF-10, SPEC-SAF-19, SPEC-RT-06
# spec: SPEC-CLM-04
import gzip
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quaoar.serp.ledger import Ledger, LlmCall, SearchRecord

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
WEEK = timedelta(days=7)
DAY = timedelta(days=1)


def record(
    ledger: Ledger, body: bytes, *, status: str = "ok", at: datetime = NOW, **kw: str
) -> SearchRecord:
    rec = SearchRecord(
        request_hash=kw.get("request_hash", "h1"),
        engine=kw.get("engine", "google"),
        params_json=kw.get("params_json", '{"q":"x"}'),
        status=status,
        search_id=kw.get("search_id", "sid1"),
        body_sha256=ledger.blobs.put(body),
        key_fp=kw.get("key_fp", "abcd1234"),
        credits=1,
        latency_ns=900_000,
        fetched_at=at,
    )
    ledger.record(rec)
    return rec


def test_round_trip_returns_the_record_and_exact_body(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    rec = record(ledger, b'{"organic_results":[]}')
    found = ledger.latest("h1", NOW + DAY, ttl=WEEK)
    assert found is not None
    assert found[0] == rec
    assert found[1] == b'{"organic_results":[]}'


def test_recording_the_same_fetch_twice_is_idempotent(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    record(ledger, b"{}")
    record(ledger, b"{}")
    assert ledger.count_searches() == 1


def test_ttl_expires_old_results(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    record(ledger, b"{}")
    assert ledger.latest("h1", NOW + WEEK + DAY, ttl=WEEK) is None


def test_empty_results_expire_after_a_day_even_with_a_long_ttl(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    record(ledger, b"{}", status="empty")
    assert ledger.latest("h1", NOW + timedelta(hours=23), ttl=WEEK) is not None
    assert ledger.latest("h1", NOW + timedelta(hours=25), ttl=WEEK) is None


def test_newest_fetch_wins(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    record(ledger, b'{"v":1}')
    record(ledger, b'{"v":2}', at=NOW + DAY, search_id="sid2")
    found = ledger.latest("h1", NOW + DAY, ttl=WEEK)
    assert found is not None
    assert found[1] == b'{"v":2}'


def test_tampered_blob_is_a_miss_and_shows_in_verify(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    rec = record(ledger, b'{"real":true}')
    blob = ledger.blobs.path_for(rec.body_sha256)
    blob.write_bytes(gzip.compress(b'{"real":false}'))
    assert ledger.latest("h1", NOW, ttl=WEEK) is None
    assert ledger.blobs.verify_all() == [rec.body_sha256]


def test_injection_shaped_values_are_stored_verbatim(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    nasty = "x'); DROP TABLE searches;--"
    record(ledger, b"{}", request_hash=nasty, params_json=nasty, search_id=nasty)
    found = ledger.latest(nasty, NOW, ttl=WEEK)
    assert found is not None
    assert found[0].params_json == nasty
    assert ledger.count_searches() == 1


def test_database_runs_in_wal_mode(tmp_path: Path) -> None:
    Ledger(tmp_path)
    with sqlite3.connect(tmp_path / "ledger.sqlite3") as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_stats_report_credits_hit_rate_and_latency(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    record(ledger, b"{}", engine="google", key_fp="aaaa0000")
    record(ledger, b"{}", request_hash="h2", engine="google_maps", key_fp="aaaa0000")
    ledger.use("scan1", "h1", cached=False, spent=1, latency_ns=4_000_000, at=NOW)
    ledger.use("scan1", "h2", cached=False, spent=1, latency_ns=2_000_000, at=NOW)
    ledger.use("scan2", "h1", cached=True, spent=0, latency_ns=50_000, at=NOW)

    stats = ledger.stats()
    assert stats.credits_by_engine == {"google": 1, "google_maps": 1}
    assert stats.credits_by_key == {"aaaa0000": 2}
    assert stats.credits_by_scan == {"scan1": 2, "scan2": 0}
    assert stats.hit_rate == 1 / 3
    assert stats.live_p50_ms == 3.0
    assert stats.live_p95_ms == 3.9


def test_llm_answers_are_cached_by_request_hash_without_expiry(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    body = b'{"items":[]}'
    call = LlmCall("r1", "command-a-03-2025", "quotes", ledger.blobs.put(body), "fp", 10, 2, 5, NOW)
    ledger.record_llm(call)
    ledger.record_llm(call)
    assert ledger.llm_body("r1") == body
    assert ledger.llm_body("missing") is None
