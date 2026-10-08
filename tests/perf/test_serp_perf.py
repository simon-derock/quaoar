# spec: SPEC-PRF-02, SPEC-PRF-03
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from quaoar.domain.ids import canonical_json, sha256_hex
from quaoar.guard.query import prepare_query
from quaoar.serp.ledger import Ledger, SearchRecord
from tests.perf.conftest import median_seconds
from tests.timing import budget_seconds

NOW = datetime(2026, 10, 9, tzinfo=UTC)


def request_hash() -> str:
    prepared = prepare_query("google", {"q": '"Oasis Corpcare" site:zaubacorp.com'})
    return sha256_hex(canonical_json({"engine": "google", **prepared}))


@pytest.mark.perf
def test_request_hash_median_under_30_microseconds(benchmark: BenchmarkFixture) -> None:
    benchmark(request_hash)
    assert median_seconds(benchmark) < budget_seconds(30e-6)


@pytest.mark.perf
def test_ledger_cache_hit_median_under_2_ms(benchmark: BenchmarkFixture, tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    body = canonical_json({"organic_results": [{"title": "x" * 200}] * 80}).encode()
    ledger.record(
        SearchRecord("h1", "google", "{}", "ok", "sid", ledger.blobs.put(body), "fp", 1, 1, NOW)
    )
    benchmark(ledger.latest, "h1", NOW, timedelta(days=7))
    assert median_seconds(benchmark) < budget_seconds(2e-3)
