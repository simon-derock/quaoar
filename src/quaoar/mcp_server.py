# quaoar as mcp tools: replayed cases need no keys; live scans obey the same budgets as the cli
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from quaoar.prospectus.acquire import IntakeError
from quaoar.replay import ReplayBundleError, load_replay
from quaoar.scoring.card import Card
from quaoar.service import Runtime, execute, intake, make_runtime, scan_folder

NAME = re.compile(r"^[a-z0-9-]{1,64}$")
MAX_MCP_CREDITS = 25
REPLAY_DIR = Path("fixtures/replay")


def build_server(
    runtime_factory: Callable[[], Runtime] = make_runtime,
    replay_dir: Path = REPLAY_DIR,
    *,
    public: bool | None = None,
) -> FastMCP:
    mcp = FastMCP("quaoar")
    read_only = os.environ.get("QUAOAR_PUBLIC_MODE") == "replay" if public is None else public

    @mcp.tool(description="Recorded cases that can be viewed with no API keys.")
    def list_replays() -> list[str]:
        return sorted(p.name for p in replay_dir.glob("*") if p.is_dir())

    @mcp.tool(
        description="The saved card of a recorded case: what checks out, what doesn't match, what couldn't be found."
    )
    def replay_card(name: str) -> dict[str, Any]:
        check_name(name)
        try:
            return load_replay(replay_dir / name)[1].model_dump(mode="json")
        except ReplayBundleError as exc:
            raise ValueError(str(exc)) from None

    @mcp.tool(description="The card of a scan finished earlier on this machine.")
    def saved_card(scan_id: str) -> dict[str, Any]:
        check_name(scan_id)
        path = scan_folder(runtime_factory(), scan_id) / "card.json"
        if not path.is_file():
            raise ValueError(f"no saved scan {scan_id}")
        return Card.model_validate_json(path.read_text(encoding="utf-8")).model_dump(mode="json")

    @mcp.tool(
        description="Check an SME IPO prospectus (local pdf path or https url) against public evidence. Uses SerpApi credits."
    )
    def scan_prospectus(source: str, max_credits: int = 15, cutoff: str = "") -> dict[str, Any]:
        if read_only:
            raise ValueError("live scans are disabled in replay mode")
        from datetime import date

        runtime = runtime_factory()
        try:
            prospectus = intake(source, runtime)
        except IntakeError as exc:
            raise ValueError(f"can't use that input: {exc}") from None
        done = execute(
            prospectus, runtime, max_credits=min(max(max_credits, 1), MAX_MCP_CREDITS),
            cutoff=date.fromisoformat(cutoff) if cutoff else None,
        )  # fmt: skip
        return {"credits": done.credits, "card": done.result.card.model_dump(mode="json")}

    @mcp.tool(description="Credits spent by engine and key fingerprint, and the cache hit rate.")
    def ledger_stats() -> dict[str, Any]:
        stats = runtime_factory().ledger.stats()
        return {
            "credits_by_engine": stats.credits_by_engine,
            "credits_by_key": stats.credits_by_key,
            "hit_rate": stats.hit_rate,
        }

    return mcp


def check_name(name: str) -> None:
    if not NAME.match(name):
        raise ValueError("names are lowercase letters, digits and hyphens only")


def serve() -> None:
    build_server().run()
