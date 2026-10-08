# spec: SPEC-GRD-01, SPEC-SAF-07
import pytest

from quaoar.guard.text import clean_text


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("plain words", "plain words"),
        ("\x1b[31mred\x1b[0m alert", "red alert"),
        ("\x1b]8;;https://evil.example\x07click\x1b]8;;\x07", "click"),
        ("\x1b]0;new title\x1b\\text", "text"),
        ("abc\u202edcb", "abcdcb"),
        ("zero\u200bwidth\ufeff", "zerowidth"),
        ("bell\x07 and nul\x00", "bell and nul"),
        ("keeps\ttabs\nand newlines", "keeps\ttabs\nand newlines"),
        ("\uff21\uff22\uff23 Ltd", "ABC Ltd"),
    ],
)
def test_strips_escapes_controls_and_bidi_then_normalizes(raw: str, clean: str) -> None:
    assert clean_text(raw).text == clean


def test_reports_how_many_characters_were_removed() -> None:
    result = clean_text("\x1b[31mred\x1b[0m")
    assert result.hits[0].guard == "G1"
    assert result.hits[0].count == 2


def test_clean_text_reports_nothing_for_clean_input() -> None:
    assert clean_text("nothing to see").hits == ()
