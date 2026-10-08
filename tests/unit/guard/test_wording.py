# spec: SPEC-GRD-06, SPEC-SC-05
import pytest

from quaoar.guard.wording import banned_terms


@pytest.mark.parametrize(
    ("text", "terms"),
    [
        ("This IPO is a scam", ["scam"]),
        ("Fraudulent vendor, avoid it", ["fraudulent", "avoid"]),
        ("a sure-shot multibagger, buy now", ["sure-shot", "multibagger", "buy"]),
        ("target price 150, invest now", ["target price", "invest now"]),
        ("yeh farzi company hai, mat kharido", ["farzi", "kharido"]),
    ],
)
def test_finds_banned_terms(text: str, terms: list[str]) -> None:
    assert banned_terms(text) == terms


@pytest.mark.parametrize(
    "text",
    [
        "Selling shareholders offer 20% of the issue.",
        "The buyer of the plant paid in advance.",
        "Facts with sources. Not investment advice.",
        "2 of 3 claimed clients could not be found on Google Maps.",
    ],
)
def test_neutral_language_passes(text: str) -> None:
    assert banned_terms(text) == []
