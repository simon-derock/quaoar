# spec: SPEC-SAN-03, SPEC-SC-05
# nothing secret, personal or accusatory ships in the committed replay bundles
import re

import pytest

from quaoar.guard.pii import AADHAAR, FREE_MAIL, MOBILE, PAN
from quaoar.guard.wording import banned_terms
from quaoar.replay import load_replay
from tests.meta.test_docstrings import ROOT

BUNDLES = sorted(p for p in (ROOT / "fixtures" / "replay").glob("*") if p.is_dir())
HASH_FIELD = re.compile(r'"(?:request|search_id|id|parent|key|sha256)":"[0-9a-f]{8,}"')
KEYLIKE = re.compile(r"api_key=(?!\[redacted\])|bearer\s+\w{8,}|\b[0-9a-f]{64}\b", re.I)


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_bundle_has_no_keys_or_personal_identifiers(bundle) -> None:  # type: ignore[no-untyped-def]
    text = "".join(f.read_text(encoding="utf-8") for f in bundle.glob("*"))
    assert KEYLIKE.search(text) is None
    # request and search ids are hex and can be all digits by chance
    text = HASH_FIELD.sub('"hash"', text)
    for pattern in (PAN, AADHAAR, MOBILE, FREE_MAIL):
        assert pattern.search(text) is None


@pytest.mark.parametrize("bundle", BUNDLES, ids=lambda p: p.name)
def test_bundle_loads_and_its_card_text_is_neutral(bundle) -> None:  # type: ignore[no-untyped-def]
    _, card = load_replay(bundle)
    assert all(banned_terms(s.text) == [] for s in card.signals)


def test_at_least_one_bundle_is_committed() -> None:
    assert BUNDLES
