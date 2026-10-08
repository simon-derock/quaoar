# spec: SPEC-CLI-01, SPEC-CLI-02, SPEC-CLI-06, SPEC-SAF-08
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quaoar.cli import app, pretty
from quaoar.domain.findings import Signal, Status
from quaoar.events import Event
from quaoar.scoring.card import build_card

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUAOAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SERPAPI_API_KEYS", "")
    return tmp_path / "home"


def test_help_lists_the_commands() -> None:
    out = runner.invoke(app, ["--help"])
    assert out.exit_code == 0
    for command in ("scan", "card", "ledger", "keys"):
        assert command in out.output


def test_bad_input_exits_with_code_two() -> None:
    out = runner.invoke(app, ["scan", "missing.pdf"])
    assert out.exit_code == 2
    assert "can't use that input" in out.output


def test_saved_card_prints_with_its_disclaimer(isolated_home: Path) -> None:
    signal = Signal(
        check="vendor",
        rule="VX-03",
        subject="V",
        status=Status.INCONSISTENT,
        text="quote is 1,770 times",
    )
    folder = isolated_home / "scans" / "q1"
    folder.mkdir(parents=True)
    (folder / "card.json").write_text(build_card("q1", "DEMO LIMITED", [signal]).model_dump_json())
    out = runner.invoke(app, ["card", "q1"])
    assert out.exit_code == 0
    assert "doesn't match" in out.output
    assert "Not investment advice" in out.output
    assert runner.invoke(app, ["card", "nope"]).exit_code == 2


def test_pretty_lines_escape_markup_from_untrusted_text() -> None:
    event = Event(
        id="s-1",
        parent=None,
        scan="s",
        t_ns=1,
        type="stage",
        data={"name": "vendor", "subject": "[red]X[/red]\x1b[2J"},
    )
    line = pretty(event)
    assert "\\[red]" in line
    assert "\x1b" not in line
