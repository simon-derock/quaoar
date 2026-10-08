# spec: SPEC-API-01, SPEC-API-02, SPEC-SAF-05, SPEC-SAF-13, SPEC-SAF-14, SPEC-SAF-15
import json

import pytest
from fastapi.testclient import TestClient

from quaoar.api.app import create_app
from tests.meta.test_docstrings import ROOT

REPLAYS = ROOT / "fixtures" / "replay"


def client(**kw: object) -> TestClient:
    return TestClient(create_app(REPLAYS, event_delay=0, **kw))  # type: ignore[arg-type]


def test_health_cases_and_card() -> None:
    c = client()
    assert c.get("/health").json() == {"status": "ok", "mode": "replay"}
    assert "trafiksol" in c.get("/api/cases").json()
    card = c.get("/api/card/trafiksol").json()
    assert card["disclaimer"].endswith("Not investment advice.")


def test_stream_sends_events_then_card_then_done() -> None:
    body = client().get("/api/scan/stream", params={"case": "trafiksol"}).text
    frames = [f for f in body.split("\n\n") if f]
    kinds = [f.split("\n")[0] for f in frames]
    assert kinds[0] == "event: event"
    assert kinds[-2:] == ["event: card", "event: done"]
    first = json.loads(frames[0].split("data: ", 1)[1])
    assert first["data"]["name"] == "intake"


@pytest.mark.parametrize("bad", ["../etc/passwd", "Trafiksol", "..%2f..", "nope", "a" * 65])
def test_bad_case_ids_are_404_not_file_reads(bad: str) -> None:
    c = client()
    assert c.get(f"/api/card/{bad}").status_code in (404, 422)
    assert c.get("/api/scan/stream", params={"case": bad}).status_code == 404


def test_public_surface_has_no_docs_no_uploads_no_live_scan() -> None:
    c = client()
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(path).status_code == 404
    assert c.post("/api/scan", content=b"%PDF").status_code in (404, 405)


def test_security_headers_and_rate_limit() -> None:
    c = client(rate_per_minute=3)
    first = c.get("/health")
    assert first.headers["x-content-type-options"] == "nosniff"
    assert first.headers["strict-transport-security"].startswith("max-age=")
    c.get("/health")
    c.get("/health")
    assert c.get("/health").status_code == 429


def test_cors_allows_only_the_configured_origin() -> None:
    c = client(cors_origin="https://quaoar.netlify.app")
    ok = c.get("/health", headers={"Origin": "https://quaoar.netlify.app"})
    other = c.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "https://quaoar.netlify.app"
    assert "access-control-allow-origin" not in other.headers
