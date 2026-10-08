# the only road to SerpApi: guard, cache, budget, key, http with retries, sanitize, ledger, event
import json
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

import httpx
from pydantic import JsonValue

from quaoar.clock import ClockPort
from quaoar.domain.ids import canonical_json, sha256_hex
from quaoar.events import Emitter
from quaoar.guard.query import prepare_query
from quaoar.serp.keys import KeyPool, KeysExhaustedError, KeyState
from quaoar.serp.ledger import Ledger, SearchRecord
from quaoar.serp.replay import ReplayStore
from quaoar.serp.sanitize import sanitize

SERPAPI_URL = "https://serpapi.com/search.json"
ACCOUNT_URL = "https://serpapi.com/account.json"
TIMEOUT_S = 30.0
RETRY_DELAYS_S = (0.5, 1.5)
DEFAULT_TTL = timedelta(days=7)
TTL = {
    "google_news": timedelta(hours=6),
    "google_finance": timedelta(days=1),
    "google_maps": timedelta(days=14),
    "google_maps_reviews": timedelta(days=14),
}


class Outcome(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    QUOTA = "quota"
    BAD_KEY = "bad_key"
    TRANSIENT = "transient"
    INVALID = "invalid"


class SerpError(RuntimeError):
    pass


class SerpInvalidError(SerpError):
    pass


class SerpTransientError(SerpError):
    pass


class CreditBudgetExceededError(SerpError):
    pass


@dataclass(frozen=True, slots=True)
class SerpResult:
    request_hash: str
    engine: str
    status: str
    search_id: str | None
    body: dict[str, JsonValue]
    credits: int
    cached: bool
    latency_ns: int


class CreditBudget:
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.spent = 0

    def check(self, amount: int = 1) -> None:
        if self.spent + amount > self.cap:
            raise CreditBudgetExceededError(f"{self.spent}/{self.cap} credits used")

    def spend(self, amount: int = 1) -> None:
        self.spent += amount


class LedgerClient:
    def __init__(
        self,
        *,
        ledger: Ledger,
        http: httpx.Client,
        clock: ClockPort,
        budget: CreditBudget,
        pool: KeyPool | None = None,
        replay: ReplayStore | None = None,
        emit: Emitter | None = None,
        scan: str = "adhoc",
        sleep: Callable[[float], None] = time.sleep,
        max_in_flight: int = 4,
    ) -> None:
        self._ledger, self._http, self._clock, self._budget = ledger, http, clock, budget
        self._pool, self._replay, self._emit, self._scan = pool, replay, emit, scan
        self._sleep = sleep
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(max_in_flight)

    # --- public ---

    def search(self, params: Mapping[str, object]) -> dict[str, JsonValue]:
        # serpapi-search-tools hands us engine inside params; any api_key it adds is ignored
        engine = str(params.get("engine", "google"))
        rest = {k: v for k, v in params.items() if k not in {"engine", "api_key", "output"}}
        return self.query(engine, rest).body

    def query(
        self, engine: str, params: Mapping[str, object], parent: str | None = None
    ) -> SerpResult:
        prepared = prepare_query(engine, params)
        params_json = canonical_json({"engine": engine, **prepared})
        request_hash = sha256_hex(params_json)
        start = self._clock.ns()

        # replay never touches the network or a key
        if self._replay is not None:
            body = json.loads(self._replay.get(request_hash))
            result = self._free(request_hash, engine, "ok", body, start)
            return self._report(result, parent, source="replay", key_fp=None)

        hit = self._ledger.latest(request_hash, self._clock.now(), TTL.get(engine, DEFAULT_TTL))
        if hit is not None:
            rec, raw = hit
            result = self._free(request_hash, engine, rec.status, json.loads(raw), start)
            return self._report(result, parent, source="ledger", key_fp=rec.key_fp)

        return self._live(engine, prepared, params_json, request_hash, start, parent)

    # --- helpers ---

    def _live(
        self,
        engine: str,
        prepared: dict[str, str],
        params_json: str,
        request_hash: str,
        start: int,
        parent: str | None,
    ) -> SerpResult:
        with self._lock:
            self._budget.check(1)
        outcome, body, key_fp = self._fetch(engine, prepared)

        clean = sanitize(engine, body)
        status = "empty" if outcome is Outcome.EMPTY else "ok"
        latency = self._clock.ns() - start
        rec = SearchRecord(
            request_hash=request_hash,
            engine=engine,
            params_json=params_json,
            status=status,
            search_id=search_id_of(clean),
            body_sha256=self._ledger.blobs.put(canonical_json(clean).encode()),
            key_fp=key_fp,
            credits=1,
            latency_ns=latency,
            fetched_at=self._clock.now(),
        )
        self._ledger.record(rec)
        with self._lock:
            self._budget.spend(1)
            if self._pool is not None:
                self._pool.spend(key_fp, 1)
        result = SerpResult(
            request_hash=request_hash,
            engine=engine,
            status=status,
            search_id=rec.search_id,
            body=clean,
            credits=1,
            cached=False,
            latency_ns=latency,
        )
        return self._report(result, parent, source="live", key_fp=key_fp)

    def _free(
        self, request_hash: str, engine: str, status: str, body: dict[str, JsonValue], start: int
    ) -> SerpResult:
        return SerpResult(
            request_hash=request_hash,
            engine=engine,
            status=status,
            search_id=search_id_of(body),
            body=body,
            credits=0,
            cached=True,
            latency_ns=self._clock.ns() - start,
        )

    def _fetch(
        self, engine: str, prepared: dict[str, str]
    ) -> tuple[Outcome, dict[str, JsonValue], str]:
        retries = 0
        while True:
            key = self._pick_key()
            outcome, body = self._call(engine, prepared, key)
            if outcome in (Outcome.OK, Outcome.EMPTY):
                return outcome, body, key.fingerprint

            # a spent or rejected key is retired for this run and the next one takes over
            if outcome in (Outcome.QUOTA, Outcome.BAD_KEY):
                with self._lock:
                    if self._pool is not None:
                        self._pool.exhaust(key.fingerprint)
                continue
            if outcome is Outcome.TRANSIENT and retries < len(RETRY_DELAYS_S):
                self._sleep(RETRY_DELAYS_S[retries])
                retries += 1
                continue
            if outcome is Outcome.TRANSIENT:
                raise SerpTransientError(f"{engine} kept failing after {retries} retries")
            raise SerpInvalidError(str(body.get("error", "invalid request")))

    def _call(
        self, engine: str, prepared: dict[str, str], key: KeyState
    ) -> tuple[Outcome, dict[str, JsonValue]]:
        query = {
            **prepared,
            "engine": engine,
            "api_key": key.secret.get_secret_value(),
            "output": "json",
        }
        # exceptions are swallowed on purpose: their messages can carry the request url and key
        try:
            with self._slots:
                response = self._http.get(SERPAPI_URL, params=query, timeout=TIMEOUT_S)
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return Outcome.TRANSIENT, {}
        if not isinstance(body, dict):
            return Outcome.TRANSIENT, {}
        return classify(response.status_code, body), body

    def _pick_key(self) -> KeyState:
        if self._pool is None:
            raise KeysExhaustedError("no SerpApi keys configured")
        with self._lock:
            return self._pool.pick()

    def _report(
        self, result: SerpResult, parent: str | None, *, source: str, key_fp: str | None
    ) -> SerpResult:
        if source != "replay":
            self._ledger.use(
                self._scan,
                result.request_hash,
                cached=result.cached,
                spent=result.credits,
                latency_ns=result.latency_ns,
                at=self._clock.now(),
            )
        if self._emit is not None:
            self._emit(
                "serp",
                {
                    "engine": result.engine,
                    "request": result.request_hash[:16],
                    "status": result.status,
                    "source": source,
                    "credits": result.credits,
                    "latency_ms": round(result.latency_ns / 1e6, 3),
                    "search_id": result.search_id,
                    "key": key_fp,
                },
                parent=parent,
            )
        return result


def classify(status_code: int, body: Mapping[str, object]) -> Outcome:
    error = str(body.get("error", "")).lower()
    if status_code == 401 or "invalid api key" in error:
        return Outcome.BAD_KEY
    if status_code == 429 or "run out of searches" in error or "hourly searches" in error:
        return Outcome.QUOTA
    if status_code >= 500:
        return Outcome.TRANSIENT
    # SerpApi answers an empty result with 200 and an error string; it still costs a credit
    if "hasn't returned any results" in error or "no results" in error:
        return Outcome.EMPTY
    if status_code >= 400 or error:
        return Outcome.INVALID
    return Outcome.OK


def account_lookup(http: httpx.Client) -> Callable[[str], int]:
    # the account endpoint is free; only the searches-left number is read, never the email
    def searches_left(key: str) -> int:
        response = http.get(ACCOUNT_URL, params={"api_key": key}, timeout=TIMEOUT_S)
        response.raise_for_status()
        return int(response.json().get("total_searches_left", 0))

    return searches_left


def search_id_of(body: Mapping[str, JsonValue]) -> str | None:
    meta = body.get("search_metadata")
    if isinstance(meta, dict) and isinstance(meta.get("id"), str):
        return str(meta["id"])
    return None
