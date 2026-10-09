# spec: SPEC-CLI-04
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from quaoar.config import Settings
from quaoar.doctor import diagnose
from quaoar.serp.ledger import Ledger
from quaoar.service import Runtime


def runtime(
    tmp_path: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    serp: tuple[str, ...] = ("serp-key-1234567890",),
    cohere: tuple[str, ...] = ("cohere-key-1234567890",),
) -> Runtime:
    settings = Settings(
        serpapi_keys=tuple(SecretStr(k) for k in serp),
        cohere_keys=tuple(SecretStr(k) for k in cohere),
        home=tmp_path,
    )
    return Runtime(settings, Ledger(tmp_path), httpx.Client(transport=httpx.MockTransport(handler)))


def good(request: httpx.Request) -> httpx.Response:
    if request.url.host == "serpapi.com":
        return httpx.Response(200, json={"total_searches_left": 200})
    return httpx.Response(200, json={"models": [{"name": "command-a-03-2025"}]})


def test_a_healthy_setup_reports_all_green_and_never_prints_keys(tmp_path: Path) -> None:
    rows = diagnose(runtime(tmp_path, good))
    assert all(ok for ok, _ in rows)
    text = " ".join(t for _, t in rows)
    assert "200 searches left" in text
    assert "model command-a-03-2025 available" in text
    assert "serp-key" not in text
    assert "cohere-key" not in text


def test_rejected_keys_and_a_missing_model_are_reported(tmp_path: Path) -> None:
    def bad(request: httpx.Request) -> httpx.Response:
        if request.url.host == "serpapi.com":
            return httpx.Response(401, json={"error": "Invalid API key"})
        return httpx.Response(200, json={"models": [{"name": "something-else"}]})

    rows = diagnose(runtime(tmp_path, bad))
    texts = [t for _, t in rows]
    assert any("rejected or unreachable" in t for t in texts)
    assert any("is not available to it" in t for t in texts)
    assert not all(ok for ok, _ in rows)


def test_missing_keys_say_what_to_set(tmp_path: Path) -> None:
    rows = diagnose(runtime(tmp_path, good, serp=(), cohere=()))
    texts = [t for _, t in rows]
    assert "no SerpApi key: set SERPAPI_API_KEYS in .env" in texts
    assert "no Cohere key: set COHERE_API_KEYS in .env" in texts


@pytest.mark.parametrize("status", [500, 429])
def test_server_errors_do_not_crash_the_check(tmp_path: Path, status: int) -> None:
    rows = diagnose(runtime(tmp_path, lambda r: httpx.Response(status)))
    assert not all(ok for ok, _ in rows)
