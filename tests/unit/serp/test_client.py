# spec: SPEC-SRP-01, SPEC-SRP-02, SPEC-SRP-03, SPEC-SRP-04, SPEC-KEY-03, SPEC-KEY-04
# spec: SPEC-RT-01, SPEC-RT-06, SPEC-RT-08, SPEC-RPL-01
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from quaoar.domain.ids import canonical_json
from quaoar.events import Emitter, MemorySink
from quaoar.guard.query import QueryRejectedError
from quaoar.serp.client import (
    CreditBudget,
    CreditBudgetExceededError,
    LedgerClient,
    Outcome,
    SerpInvalidError,
    SerpTransientError,
    account_lookup,
    classify,
)
from quaoar.serp.keys import KeyPool, fingerprint
from quaoar.serp.ledger import Ledger
from quaoar.serp.replay import ReplayMissError, ReplayStore, write_bundle
from tests.fakes import FixedClock

OK_BODY = {
    "search_metadata": {
        "id": "sid-1",
        "json_endpoint": "https://serpapi.com/searches/sid-1.json?api_key=key-aaaa",
    },
    "organic_results": [{"title": "Trafiksol order", "link": "https://www.sebi.gov.in/x.html"}],
}
EMPTY_BODY = {
    "search_metadata": {"id": "sid-2"},
    "error": "Google hasn't returned any results for this query.",
}

Handler = Callable[[httpx.Request], httpx.Response]


class Harness:
    def __init__(self, tmp_path: Path, handler: Handler, *, cap: int = 10, left: int = 100) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []
        self.sink = MemorySink()
        self.clock = FixedClock()

        def record(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        self.pool = KeyPool(
            [SecretStr("key-aaaa"), SecretStr("key-bbbb")],
            reserve=0,
            searches_left=lambda key: left if key == "key-aaaa" else left - 1,
        )
        self.budget = CreditBudget(cap)
        self.ledger = Ledger(tmp_path / "home")
        self.client = LedgerClient(
            ledger=self.ledger,
            http=httpx.Client(transport=httpx.MockTransport(record)),
            clock=self.clock,
            budget=self.budget,
            pool=self.pool,
            emit=Emitter("scan1", self.sink, self.clock),
            scan="scan1",
            sleep=self.sleeps.append,
        )


def ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=OK_BODY)


def test_live_call_sends_key_and_returns_a_sanitized_body(tmp_path: Path) -> None:
    h = Harness(tmp_path, ok)
    result = h.client.query("google", {"q": "trafiksol"})

    sent = h.requests[0].url.params
    assert sent["api_key"] == "key-aaaa"
    assert (sent["engine"], sent["output"], sent["gl"]) == ("google", "json", "in")
    assert (result.credits, result.cached, result.search_id) == (1, False, "sid-1")
    assert "key-aaaa" not in str(result.body)
    assert h.budget.spent == 1


def test_second_identical_query_is_free_and_skips_the_network(tmp_path: Path) -> None:
    h = Harness(tmp_path, ok)
    first = h.client.query("google", {"q": "trafiksol"})
    second = h.client.query("google", {"q": "trafiksol"})
    assert len(h.requests) == 1
    assert (second.cached, second.credits) == (True, 0)
    assert second.body == first.body
    assert second.request_hash == first.request_hash


def test_events_carry_cost_and_provenance_but_never_the_key(tmp_path: Path) -> None:
    h = Harness(tmp_path, ok)
    h.client.query("google", {"q": "trafiksol"}, parent="scan1-000001")
    event = h.sink.events[0]
    assert event.type == "serp"
    assert event.parent == "scan1-000001"
    assert event.data["credits"] == 1
    assert event.data["search_id"] == "sid-1"
    assert event.data["key"] == fingerprint("key-aaaa")
    assert "key-aaaa" not in event.model_dump_json()


def test_quota_error_rotates_to_the_next_key(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["api_key"] == "key-aaaa":
            return httpx.Response(429, json={"error": "Your account has run out of searches."})
        return httpx.Response(200, json=OK_BODY)

    h = Harness(tmp_path, handler)
    result = h.client.query("google", {"q": "trafiksol"})
    assert result.status == "ok"
    assert [r.url.params["api_key"] for r in h.requests] == ["key-aaaa", "key-bbbb"]
    assert {s.fingerprint: s.exhausted for s in h.pool.status()}[fingerprint("key-aaaa")]


def test_transient_failures_retry_with_backoff_then_succeed(tmp_path: Path) -> None:
    replies = iter(
        [
            httpx.Response(503),
            httpx.Response(200, text="not json"),
            httpx.Response(200, json=OK_BODY),
        ]
    )
    h = Harness(tmp_path, lambda _: next(replies))
    assert h.client.query("google", {"q": "x"}).status == "ok"
    assert h.sleeps == [0.5, 1.5]


def test_persistent_failure_raises_without_spending_or_caching(tmp_path: Path) -> None:
    h = Harness(tmp_path, lambda _: httpx.Response(502))
    with pytest.raises(SerpTransientError):
        h.client.query("google", {"q": "x"})
    assert h.budget.spent == 0
    assert h.ledger.count_searches() == 0


def test_empty_result_costs_a_credit_and_is_negative_cached(tmp_path: Path) -> None:
    h = Harness(tmp_path, lambda _: httpx.Response(200, json=EMPTY_BODY))
    first = h.client.query("google", {"q": "nothing here"})
    second = h.client.query("google", {"q": "nothing here"})
    assert (first.status, first.credits) == ("empty", 1)
    assert (second.cached, len(h.requests)) == (True, 1)


def test_invalid_request_raises_and_is_not_cached(tmp_path: Path) -> None:
    h = Harness(tmp_path, lambda _: httpx.Response(400, json={"error": "Unsupported parameter."}))
    with pytest.raises(SerpInvalidError):
        h.client.query("google", {"q": "x"})
    assert h.ledger.count_searches() == 0


def test_credit_cap_stops_before_any_network_call(tmp_path: Path) -> None:
    h = Harness(tmp_path, ok, cap=1)
    h.client.query("google", {"q": "one"})
    with pytest.raises(CreditBudgetExceededError):
        h.client.query("google", {"q": "two"})
    assert len(h.requests) == 1


def test_query_guard_runs_before_anything_else(tmp_path: Path) -> None:
    h = Harness(tmp_path, ok)
    with pytest.raises(QueryRejectedError):
        h.client.query("google", {"q": "site:evil.example x"})
    assert h.requests == []


def test_search_protocol_for_serpapi_search_tools_ignores_their_api_key(tmp_path: Path) -> None:
    h = Harness(tmp_path, ok)
    body = h.client.search({"engine": "google", "q": "x", "api_key": "theirs", "output": "json"})
    assert body["search_metadata"] == {
        "id": "sid-1",
        "json_endpoint": "https://serpapi.com/searches/sid-1.json?api_key=[redacted]",
    }
    assert h.requests[0].url.params["api_key"] == "key-aaaa"


def test_emptying_the_cache_changes_credits_never_results(tmp_path: Path) -> None:
    warm = Harness(tmp_path / "warm", ok)
    warm.client.query("google", {"q": "x"})
    warm_again = warm.client.query("google", {"q": "x"})
    cold = Harness(tmp_path / "cold", ok).client.query("google", {"q": "x"})
    assert warm_again.body == cold.body
    assert (warm_again.credits, cold.credits) == (0, 1)


def test_replay_answers_without_keys_or_network(tmp_path: Path) -> None:
    h = Harness(tmp_path, ok)
    live = h.client.query("google", {"q": "x"})
    bundle = tmp_path / "bundle"
    write_bundle(bundle, {live.request_hash: canonical_json(live.body).encode()})

    replay_client = LedgerClient(
        ledger=Ledger(tmp_path / "other"),
        http=httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("network used"))),
        clock=FixedClock(),
        budget=CreditBudget(0),
        replay=ReplayStore(bundle),
    )
    replayed = replay_client.query("google", {"q": "x"})
    assert (replayed.body, replayed.credits) == (live.body, 0)
    with pytest.raises(ReplayMissError):
        replay_client.query("google", {"q": "never recorded"})


@pytest.mark.parametrize(
    ("status", "body", "outcome"),
    [
        (200, {"organic_results": []}, Outcome.OK),
        (200, {"error": "Google hasn't returned any results for this query."}, Outcome.EMPTY),
        (401, {"error": "Invalid API key."}, Outcome.BAD_KEY),
        (429, {}, Outcome.QUOTA),
        (200, {"error": "Your account has run out of searches."}, Outcome.QUOTA),
        (503, {}, Outcome.TRANSIENT),
        (400, {"error": "Missing query `q` parameter."}, Outcome.INVALID),
    ],
)
def test_classify_maps_serpapi_answers_to_outcomes(
    status: int, body: dict[str, str], outcome: Outcome
) -> None:
    assert classify(status, body) == outcome


def test_account_lookup_reads_only_searches_left() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/account.json"
        return httpx.Response(200, json={"total_searches_left": 249, "account_email": "x@y.z"})

    lookup = account_lookup(httpx.Client(transport=httpx.MockTransport(handler)))
    assert lookup("key-aaaa") == 249
