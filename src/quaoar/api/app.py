# public api: replays recorded cases as server-sent events; holds no keys and runs no live scans
import asyncio
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from quaoar.events import Event
from quaoar.replay import ReplayBundleError, load_replay
from quaoar.scoring.card import Card

CASE_ID = re.compile(r"^[a-z0-9-]{1,64}$")
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cache-Control": "no-store",
}
RATE_PER_MINUTE = 30
EVENT_DELAY_S = 0.12


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self._limit = per_minute
        self._seen: dict[str, list[float]] = {}

    def allow(self, client: str, now: float) -> bool:
        recent = [t for t in self._seen.get(client, []) if now - t < 60]
        if len(recent) >= self._limit:
            self._seen[client] = recent
            return False
        self._seen[client] = [*recent, now]
        return True


def create_app(
    replay_dir: Path,
    cors_origin: str = "",
    rate_per_minute: int = RATE_PER_MINUTE,
    event_delay: float = EVENT_DELAY_S,
) -> FastAPI:
    # no interactive docs or schema routes on the public surface
    app = FastAPI(title="quaoar", docs_url=None, redoc_url=None, openapi_url=None)
    if cors_origin:
        app.add_middleware(
            CORSMiddleware, allow_origins=[cors_origin], allow_methods=["GET"], allow_headers=[]
        )
    install_guard(app, RateLimiter(rate_per_minute))
    add_routes(app, replay_dir, event_delay)
    return app


def install_guard(app: FastAPI, limiter: RateLimiter) -> None:
    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client, time.monotonic()):
            return JSONResponse({"error": "slow down", "request": request_id()}, 429, HEADERS)
        try:
            response = await call_next(request)
        except Exception:
            return JSONResponse(
                {"error": "something went wrong", "request": request_id()}, 500, HEADERS
            )
        response.headers.update(HEADERS)
        return response


def find_bundle(replay_dir: Path, case: str) -> Path:
    # the id shape is checked and the resolved path must stay inside the fixtures folder
    if not CASE_ID.match(case):
        raise HTTPException(404, "no such case")
    path = (replay_dir / case).resolve()
    if replay_dir.resolve() not in path.parents or not path.is_dir():
        raise HTTPException(404, "no such case")
    return path


def add_routes(app: FastAPI, replay_dir: Path, event_delay: float) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "replay"}

    @app.get("/api/cases")
    def cases() -> list[str]:
        return sorted(p.name for p in replay_dir.glob("*") if p.is_dir())

    @app.get("/api/card/{case}")
    def card(case: str) -> JSONResponse:
        _, saved = load_or_404(find_bundle(replay_dir, case))
        return JSONResponse(saved.model_dump(mode="json"))

    @app.get("/api/scan/stream")
    def stream(case: str) -> StreamingResponse:
        events, saved = load_or_404(find_bundle(replay_dir, case))

        async def frames() -> AsyncIterator[str]:
            for event in events:
                yield f"event: event\ndata: {event.model_dump_json()}\n\n"
                await asyncio.sleep(event_delay)
            yield f"event: card\ndata: {saved.model_dump_json()}\n\n"
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(frames(), media_type="text/event-stream", headers=HEADERS)


def load_or_404(bundle: Path) -> tuple[list[Event], Card]:
    try:
        return load_replay(bundle)
    except ReplayBundleError:
        raise HTTPException(404, "no such case") from None


def request_id() -> str:
    return f"{time.time_ns():x}"[-10:]
