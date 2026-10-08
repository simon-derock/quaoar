# spec: SPEC-DOM-01
from hypothesis import given
from hypothesis import strategies as st

from quaoar.domain.ids import canonical_json, sha256_hex, stable_id


def test_key_order_does_not_change_the_id() -> None:
    assert stable_id({"a": 1, "b": 2}) == stable_id({"b": 2, "a": 1})


def test_id_is_sixteen_lowercase_hex_chars() -> None:
    value = stable_id({"engine": "google", "q": "trafiksol"})
    assert len(value) == 16
    assert value == value.lower()
    int(value, 16)


def test_canonical_json_is_compact_and_keeps_unicode() -> None:
    assert canonical_json({"b": "₹", "a": [1, 2]}) == '{"a":[1,2],"b":"₹"}'


def test_sha256_matches_the_standard_vector() -> None:
    assert sha256_hex("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_hex(b"abc") == sha256_hex("abc")


@given(st.dictionaries(st.text(max_size=8), st.integers(), max_size=8))
def test_same_content_always_gives_the_same_id(data: dict[str, int]) -> None:
    reordered = dict(reversed(list(data.items())))
    assert stable_id(data) == stable_id(reordered)
