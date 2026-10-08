# spec: SPEC-KEY-01, SPEC-KEY-02, SPEC-KEY-03
import pytest
from pydantic import SecretStr

from quaoar.serp.keys import KeyPool, KeysExhaustedError, fingerprint

LEFT = {"key-aaaa": 10, "key-bbbb": 200, "key-cccc": 3}


def pool(reserve: int = 5) -> KeyPool:
    keys = [SecretStr(k) for k in LEFT]
    return KeyPool(keys, reserve=reserve, searches_left=lambda key: LEFT[key])


def test_fingerprint_is_eight_hex_chars_and_hides_the_key() -> None:
    fp = fingerprint("key-aaaa")
    assert len(fp) == 8
    assert "key" not in fp


def test_picks_the_key_with_most_searches_left() -> None:
    picked = pool().pick()
    assert picked.fingerprint == fingerprint("key-bbbb")
    assert picked.secret.get_secret_value() == "key-bbbb"


def test_keys_at_or_below_the_reserve_are_skipped() -> None:
    p = pool(reserve=10)
    p.exhaust(fingerprint("key-bbbb"))
    with pytest.raises(KeysExhaustedError):
        p.pick()


def test_exhausted_key_rotates_to_the_next_best() -> None:
    p = pool()
    p.exhaust(fingerprint("key-bbbb"))
    assert p.pick().fingerprint == fingerprint("key-aaaa")


def test_spending_lowers_the_local_count() -> None:
    p = pool()
    p.spend(fingerprint("key-bbbb"), 195)
    assert p.pick().fingerprint == fingerprint("key-aaaa")


def test_status_shows_fingerprints_only() -> None:
    rows = pool().status()
    assert {r.fingerprint for r in rows} == {fingerprint(k) for k in LEFT}
    assert all("key-" not in repr(r) for r in rows)


def test_account_lookup_failure_counts_as_zero_left() -> None:
    def broken(key: str) -> int:
        raise OSError("offline")

    with pytest.raises(KeysExhaustedError):
        KeyPool([SecretStr("key-aaaa")], reserve=0, searches_left=broken).pick()


def test_no_keys_at_all_is_exhausted() -> None:
    with pytest.raises(KeysExhaustedError):
        KeyPool([], reserve=0, searches_left=lambda key: 0).pick()
