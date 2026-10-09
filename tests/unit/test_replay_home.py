# spec: SPEC-RPL-02, SPEC-MCP-01
import filecmp
from pathlib import Path

import pytest

from quaoar.replay import BUNDLED_CASES, find_case, replay_home
from tests.meta.test_docstrings import ROOT

FIXTURES = ROOT / "fixtures" / "replay"


def test_the_package_ships_the_same_cases_as_the_fixtures() -> None:
    names = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())
    assert names == sorted(p.name for p in BUNDLED_CASES.iterdir() if p.is_dir())
    for name in names:
        _, mismatch, errors = filecmp.cmpfiles(
            FIXTURES / name, BUNDLED_CASES / name, ["events.jsonl", "card.json"], shallow=False
        )
        assert (mismatch, errors) == ([], []), name


def test_outside_a_clone_the_bundled_cases_are_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert replay_home() == BUNDLED_CASES
    assert find_case(Path("trafiksol")) == BUNDLED_CASES / "trafiksol"


def test_a_path_is_used_as_given(tmp_path: Path) -> None:
    assert find_case(tmp_path) == tmp_path
    assert find_case(Path("some/where")) == Path("some/where")
