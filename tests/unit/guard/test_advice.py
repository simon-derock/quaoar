# spec: SPEC-GRD-07
import pytest

from quaoar.guard.advice import ADVICE_REPLY, advice_request


@pytest.mark.parametrize(
    "text",
    [
        "Should I apply for this IPO?",
        "should i buy trafiksol",
        "what is the target price?",
        "will it list at a premium",
        "is this a multibagger",
        "listing gains kitne honge?",
        "kya main apply karu?",
    ],
)
def test_detects_requests_for_advice(text: str) -> None:
    hit = advice_request(text)
    assert hit is not None
    assert hit.guard == "G8"


@pytest.mark.parametrize(
    "text",
    [
        "check trafiksol.pdf",
        "who is the lead manager and what happened to their past issues?",
        "show proof for 2",
    ],
)
def test_ordinary_requests_pass(text: str) -> None:
    assert advice_request(text) is None


def test_reply_is_neutral() -> None:
    assert "investment advice" in ADVICE_REPLY
