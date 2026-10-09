# spec: SPEC-MCP-01, SPEC-MCP-02, SPEC-MCP-03, SPEC-SAF-13, SPEC-SKL-01
import asyncio
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.exceptions import ToolError

from quaoar.mcp_server import build_server
from quaoar.service import make_runtime
from tests.meta.test_docstrings import ROOT

REPLAYS = ROOT / "fixtures" / "replay"


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("QUAOAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SERPAPI_API_KEYS", "")
    return build_server(lambda: make_runtime(tmp_path / "no.env"), REPLAYS, public=False)


def call(server, tool: str, args: dict[str, object] | None = None):  # type: ignore[no-untyped-def]
    async def go() -> CallToolResult:
        async with Client(server) as client:
            result: CallToolResult = await client.call_tool(tool, args or {})
            return result

    return asyncio.run(go())


def test_tools_are_listed(server) -> None:  # type: ignore[no-untyped-def]
    async def names() -> set[str]:
        async with Client(server) as client:
            return {t.name for t in await client.list_tools()}

    assert asyncio.run(names()) >= {
        "list_replays",
        "replay_card",
        "scan_prospectus",
        "saved_card",
        "ledger_stats",
        "ask_card",
    }


def test_replay_card_needs_no_keys(server) -> None:  # type: ignore[no-untyped-def]
    assert "trafiksol" in call(server, "list_replays").data
    card = call(server, "replay_card", {"name": "trafiksol"}).data
    assert card["inconsistent"] >= 1
    assert card["disclaimer"].endswith("Not investment advice.")


@pytest.mark.parametrize("bad", ["../etc/passwd", "Trafiksol", "a/b", "x" * 65])
def test_names_are_validated_against_traversal(server, bad: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ToolError):
        call(server, "replay_card", {"name": bad})


def test_live_scans_are_denied_in_replay_mode(tmp_path: Path) -> None:
    locked = build_server(lambda: make_runtime(tmp_path / "no.env"), REPLAYS, public=True)
    with pytest.raises(ToolError, match="disabled"):
        call(locked, "scan_prospectus", {"source": "x.pdf"})


def test_bad_scan_input_is_a_clean_error(server) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ToolError, match="can't use that input"):
        call(server, "scan_prospectus", {"source": "missing.pdf"})


def test_ledger_stats_are_available(server) -> None:  # type: ignore[no-untyped-def]
    assert "hit_rate" in call(server, "ledger_stats").data


def test_skill_file_has_frontmatter_and_the_language_rules() -> None:
    text = (ROOT / "skills" / "quaoar" / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("---")[1]
    assert "name: quaoar" in head
    assert "description:" in head
    assert "Not investment advice" in text


def test_ask_card_answers_with_citations_and_refuses_advice(server) -> None:  # type: ignore[no-untyped-def]
    reply = call(server, "ask_card", {"name": "trafiksol", "question": "why was it flagged?"}).data
    assert reply["mode"] == "evidence"
    assert "1,770 times" in reply["answer"]
    assert reply["cites"][0]["url"].startswith("https://")
    advice = call(server, "ask_card", {"name": "trafiksol", "question": "should I apply?"}).data
    assert advice["mode"] == "fixed"
    with pytest.raises(ToolError):
        call(server, "ask_card", {"name": "../etc", "question": "hi"})
