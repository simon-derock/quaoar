# provenance ledger: each SerpApi response stored once by hash, each use of it recorded
import gzip
import sqlite3
import statistics
import threading
from dataclasses import astuple, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from quaoar.domain.ids import sha256_hex

EMPTY_TTL = timedelta(hours=24)
SCHEMA = (
    """CREATE TABLE IF NOT EXISTS searches (
        request_hash TEXT NOT NULL, engine TEXT NOT NULL, params_json TEXT NOT NULL,
        status TEXT NOT NULL, search_id TEXT, body_sha256 TEXT NOT NULL, key_fp TEXT NOT NULL,
        credits INTEGER NOT NULL, latency_ns INTEGER NOT NULL, fetched_at TEXT NOT NULL,
        PRIMARY KEY (request_hash, fetched_at))""",
    """CREATE TABLE IF NOT EXISTS llm_calls (
        request_hash TEXT PRIMARY KEY, model TEXT NOT NULL, task TEXT NOT NULL,
        body_sha256 TEXT NOT NULL, key_fp TEXT NOT NULL, input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL, latency_ns INTEGER NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS uses (
        scan TEXT NOT NULL, request_hash TEXT NOT NULL, cached INTEGER NOT NULL,
        credits INTEGER NOT NULL, latency_ns INTEGER NOT NULL, used_at TEXT NOT NULL)""",
)
# full statements as literals: no SQL is ever assembled from strings at runtime
INSERT_SEARCH = (
    "INSERT OR IGNORE INTO searches (request_hash, engine, params_json, status, search_id, "
    "body_sha256, key_fp, credits, latency_ns, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
)
INSERT_LLM = (
    "INSERT OR IGNORE INTO llm_calls (request_hash, model, task, body_sha256, key_fp, "
    "input_tokens, output_tokens, latency_ns, created_at) VALUES (?,?,?,?,?,?,?,?,?)"
)
SELECT_LLM = "SELECT body_sha256 FROM llm_calls WHERE request_hash = ?"
SELECT_LATEST = (
    "SELECT request_hash, engine, params_json, status, search_id, body_sha256, key_fp, "
    "credits, latency_ns, fetched_at FROM searches WHERE request_hash = ? "
    "ORDER BY fetched_at DESC LIMIT 1"
)


class BlobCorruptError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SearchRecord:
    request_hash: str
    engine: str
    params_json: str
    status: str
    search_id: str | None
    body_sha256: str
    key_fp: str
    credits: int
    latency_ns: int
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class LlmCall:
    request_hash: str
    model: str
    task: str
    body_sha256: str
    key_fp: str
    input_tokens: int
    output_tokens: int
    latency_ns: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LedgerStats:
    credits_by_engine: dict[str, int]
    credits_by_key: dict[str, int]
    credits_by_scan: dict[str, int]
    hit_rate: float
    live_p50_ms: float
    live_p95_ms: float


class BlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def put(self, data: bytes) -> str:
        digest = sha256_hex(data)
        path = self.path_for(digest)
        if path.exists():
            return digest

        # write then rename, so a crash never leaves half a blob behind
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(data))
        tmp.replace(path)
        return digest

    def get(self, digest: str) -> bytes:
        data = gzip.decompress(self.path_for(digest).read_bytes())
        if sha256_hex(data) != digest:
            raise BlobCorruptError(digest)
        return data

    def path_for(self, digest: str) -> Path:
        return self._root / digest[:2] / f"{digest[2:]}.json.gz"

    def verify_all(self) -> list[str]:
        bad = []
        for path in sorted(self._root.glob("*/*.json.gz")):
            digest = path.parent.name + path.name.removesuffix(".json.gz")
            try:
                self.get(digest)
            except (BlobCorruptError, OSError, EOFError):
                bad.append(digest)
        return bad


class Ledger:
    def __init__(self, home: Path) -> None:
        home.mkdir(parents=True, exist_ok=True)
        self.blobs = BlobStore(home / "blobs")
        self._lock = threading.Lock()
        self._db = sqlite3.connect(home / "ledger.sqlite3", check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        for statement in SCHEMA:
            self._db.execute(statement)
        self._db.commit()

    def record(self, rec: SearchRecord) -> None:
        # same request fetched at the same instant is the same fact, so a replayed write is a no-op
        row = (*astuple(rec)[:-1], rec.fetched_at.isoformat())
        with self._lock:
            self._db.execute(INSERT_SEARCH, row)
            self._db.commit()

    def latest(
        self, request_hash: str, now: datetime, ttl: timedelta
    ) -> tuple[SearchRecord, bytes] | None:
        with self._lock:
            row = self._db.execute(SELECT_LATEST, (request_hash,)).fetchone()
        if row is None:
            return None

        rec = to_record(row)
        limit = EMPTY_TTL if rec.status == "empty" else ttl
        if now - rec.fetched_at > limit:
            return None

        # a tampered or truncated blob is treated as never fetched
        try:
            return rec, self.blobs.get(rec.body_sha256)
        except (BlobCorruptError, OSError, EOFError):
            return None

    def record_llm(self, call: "LlmCall") -> None:
        # llm answers are cached forever: same model, task and text give the same claims
        row = (*astuple(call)[:-1], call.created_at.isoformat())
        with self._lock:
            self._db.execute(INSERT_LLM, row)
            self._db.commit()

    def llm_body(self, request_hash: str) -> bytes | None:
        with self._lock:
            row = self._db.execute(SELECT_LLM, (request_hash,)).fetchone()
        if row is None:
            return None
        try:
            return self.blobs.get(str(row[0]))
        except (BlobCorruptError, OSError, EOFError):
            return None

    def use(
        self,
        scan: str,
        request_hash: str,
        *,
        cached: bool,
        spent: int,
        latency_ns: int,
        at: datetime,
    ) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO uses VALUES (?,?,?,?,?,?)",
                (scan, request_hash, int(cached), spent, latency_ns, at.isoformat()),
            )
            self._db.commit()

    def count_searches(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(*) FROM searches").fetchone()[0])

    def stats(self) -> LedgerStats:
        with self._lock:
            by_engine = self._db.execute(
                "SELECT engine, SUM(credits) FROM searches GROUP BY engine"
            ).fetchall()
            by_key = self._db.execute(
                "SELECT key_fp, SUM(credits) FROM searches GROUP BY key_fp"
            ).fetchall()
            by_scan = self._db.execute(
                "SELECT scan, SUM(credits) FROM uses GROUP BY scan"
            ).fetchall()
            uses = self._db.execute("SELECT cached, latency_ns FROM uses").fetchall()
        live = [ns / 1e6 for cached, ns in uses if not cached]
        return LedgerStats(
            credits_by_engine=dict(by_engine),
            credits_by_key=dict(by_key),
            credits_by_scan=dict(by_scan),
            hit_rate=sum(c for c, _ in uses) / len(uses) if uses else 0.0,
            live_p50_ms=percentile(live, 50),
            live_p95_ms=percentile(live, 95),
        )


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return round(statistics.quantiles(values, n=100, method="inclusive")[pct - 1], 3)


def to_record(row: tuple[object, ...]) -> SearchRecord:
    rh, engine, params, status, sid, sha, fp, spent, latency, fetched = row
    return SearchRecord(
        request_hash=str(rh),
        engine=str(engine),
        params_json=str(params),
        status=str(status),
        search_id=None if sid is None else str(sid),
        body_sha256=str(sha),
        key_fp=str(fp),
        credits=int(str(spent)),
        latency_ns=int(str(latency)),
        fetched_at=datetime.fromisoformat(str(fetched)),
    )
