# spec: SPEC-AG-02, SPEC-RT-01
# SerpApi's own agent tools run through our client, so cache, keys and budget still apply
import json
from pathlib import Path

import httpx
from pydantic import SecretStr
from serpapi_search_tools import maps_search, news_search, videos_search, web_search

from quaoar.serp.client import CreditBudget, LedgerClient
from quaoar.serp.keys import KeyPool
from quaoar.serp.ledger import Ledger
from tests.fakes import FixedClock

BODY = {
    "search_metadata": {"id": "sid-1"},
    "organic_results": [{"title": f"r{i}", "link": f"https://e.example/{i}"} for i in range(30)],
    "news_results": [{"title": "n"}],
    "local_results": [{"title": "Oasis Corpcare", "address": "Mumbai"}],
    "video_results": [{"title": "IPO GMP today"}],
}


def client(tmp_path: Path, seen: list[httpx.Request]) -> LedgerClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=BODY)

    return LedgerClient(
        ledger=Ledger(tmp_path),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=FixedClock(),
        budget=CreditBudget(10),
        pool=KeyPool([SecretStr("key-aaaa")], reserve=0, searches_left=lambda key: 100),
    )


def test_each_tool_reaches_serpapi_through_the_ledger_client(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    ours = client(tmp_path, seen)
    tools = [
        web_search(
            provider="function", client=ours, response_format="json", allowed_engines=["google"]
        ),
        news_search(provider="function", client=ours, response_format="json"),
        maps_search(provider="function", client=ours, response_format="json"),
        videos_search(provider="function", client=ours, response_format="json"),
    ]
    for tool in tools:
        tool(query="trafiksol")

    engines = [r.url.params["engine"] for r in seen]
    assert engines == ["google", "google_news", "google_maps", "youtube"]
    assert all(r.url.params["api_key"] == "key-aaaa" for r in seen)


def test_tool_output_is_compacted_json_for_the_model(tmp_path: Path) -> None:
    tool = web_search(
        provider="function",
        client=client(tmp_path, []),
        response_format="json",
        allowed_engines=["google"],
        result_limit=5,
    )
    out = json.loads(tool(query="trafiksol"))
    assert len(out["organic_results"]) == 5


def test_repeat_tool_calls_are_served_from_the_ledger(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    tool = news_search(provider="function", client=client(tmp_path, seen), response_format="json")
    tool(query="trafiksol sebi")
    tool(query="trafiksol sebi")
    assert len(seen) == 1
