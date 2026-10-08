# spec: SPEC-RPL-02, SPEC-CLI-05, SPEC-SAF-03, SPEC-SAF-04
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quaoar.cli import app
from quaoar.domain.findings import Signal, Status
from quaoar.replay import ReplayBundleError, export_scan, load_replay
from quaoar.scoring.card import build_card

runner = CliRunner()
SECRET = "serp-secret-value-1234567890"


def finished_scan(root: Path) -> Path:
    folder = root / "scan"
    folder.mkdir()
    event = {"v": 1, "id": "s-000001", "parent": None, "scan": "s", "t_ns": 5, "type": "stage",
             "data": {"name": f"call https://x/?api_key={SECRET} PAN ABCDE1234F"}}  # fmt: skip
    (folder / "events.jsonl").write_text(json.dumps(event) + "\n")
    signal = Signal(
        check="vendor",
        rule="VX-03",
        subject="V",
        status=Status.INCONSISTENT,
        text=f"quote vs capital {SECRET}",
    )
    (folder / "card.json").write_text(build_card("s", "DEMO LIMITED", [signal]).model_dump_json())
    return folder


def test_export_scrubs_secrets_and_identifiers(tmp_path: Path) -> None:
    out = export_scan(finished_scan(tmp_path), tmp_path / "bundle", [SECRET])
    text = (out / "events.jsonl").read_text() + (out / "card.json").read_text()
    assert SECRET not in text
    assert "ABCDE1234F" not in text


def test_replay_loads_the_same_card_every_time(tmp_path: Path) -> None:
    out = export_scan(finished_scan(tmp_path), tmp_path / "bundle", [SECRET])
    first, second = load_replay(out), load_replay(out)
    assert first[1].model_dump_json() == second[1].model_dump_json()
    assert first[0] == second[0]


def test_unfinished_or_broken_bundles_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ReplayBundleError):
        export_scan(tmp_path, tmp_path / "x", [])
    with pytest.raises(ReplayBundleError):
        load_replay(tmp_path / "nothing")


def test_replay_command_prints_events_and_card_without_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUAOAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SERPAPI_API_KEYS", "")
    out = export_scan(finished_scan(tmp_path), tmp_path / "bundle", [SECRET])
    result = runner.invoke(app, ["replay", str(out)])
    assert result.exit_code == 0
    assert "doesn't match" in result.output
    assert runner.invoke(app, ["replay", str(tmp_path / "nope")]).exit_code == 2
