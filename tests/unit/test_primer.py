# spec: SPEC-ACL-03, SPEC-GRD-07
import pytest

from quaoar.guard.wording import banned_terms
from quaoar.primer import answer


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hi", "checks an SME IPO"),
        ("what is this?", "checks an SME IPO"),
        ("i know nothing about ipo, help me", "checks an SME IPO"),
        ("ipo kya hai", "checks an SME IPO"),
        ("mujhe kuch nahi pata", "checks an SME IPO"),
        ("prospectus kahan se milega", "lead manager"),
        ("ipo kaise check kare", "/replay trafiksol"),
        ("what is an SME IPO", "NSE Emerge"),
        ("what is a prospectus", "red herring"),
        ("what is drhp", "red herring"),
        ("where do i get the prospectus", "lead manager"),
        ("can you check Zomato", "lead manager"),
        ("how do I check an ipo", "/replay trafiksol"),
        ("what does couldn't find mean", "never counted against"),
        ("is Trafiksol ipo safe", "doesn't say whether an IPO is safe"),
        ("is this company legit?", "doesn't say whether an IPO is safe"),
        ("thanks", "Not investment advice"),
    ],
)
def test_beginner_questions_get_a_plain_answer(text: str, expected: str) -> None:
    reply = answer(text)
    assert reply is not None
    assert expected in reply


@pytest.mark.parametrize("text", ["", "asdf qwerty", "/replay trafiksol", "show proof for 2"])
def test_other_text_is_left_to_the_router(text: str) -> None:
    assert answer(text) is None


def test_no_answer_gives_a_view_or_uses_accusing_words() -> None:
    for text in ("hi", "what is an sme ipo", "is it safe", "how do i check", "thanks"):
        reply = answer(text) or ""
        assert banned_terms(reply) == []
        assert "you should buy" not in reply.lower()


def test_web_answers_name_no_terminal_commands_and_stay_neutral() -> None:
    for text in ("hi", "how do I check an ipo", "where do i get the prospectus", "is it safe"):
        reply = answer(text, web=True) or ""
        assert "/" not in reply
        assert banned_terms(reply) == []
    assert "recorded case" in (answer("hi", web=True) or "")
    assert "/replay" in (answer("hi") or "")
