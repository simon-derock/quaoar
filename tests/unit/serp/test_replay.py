# spec: SPEC-RPL-01
from pathlib import Path

import pytest

from quaoar.serp.replay import ReplayMissError, ReplayStore, write_bundle


def test_bundle_round_trips_bodies_by_request_hash(tmp_path: Path) -> None:
    write_bundle(tmp_path, {"h1": b'{"a":1}', "h2": b'{"b":2}'})
    store = ReplayStore(tmp_path)
    assert store.get("h1") == b'{"a":1}'
    assert store.get("h2") == b'{"b":2}'


def test_unknown_request_is_a_miss_never_a_network_call(tmp_path: Path) -> None:
    write_bundle(tmp_path, {"h1": b"{}"})
    with pytest.raises(ReplayMissError):
        ReplayStore(tmp_path).get("nope")
