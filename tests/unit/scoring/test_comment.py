# spec: SPEC-CM-01, SPEC-SC-05, SPEC-SAF-04
from quaoar.domain.findings import Evidence, Signal, Status
from quaoar.guard.wording import banned_terms
from quaoar.scoring.card import build_card
from quaoar.scoring.comment import draft_comment

PROOF = Evidence(
    engine="duckduckgo", request="r" * 16, search_id="abc123", url="https://www.instafinancials.com/company/x",
    title="X PRIVATE LIMITED - U1", snippet="paid up capital is 1 lakh",
)  # fmt: skip


def sig(
    rule: str,
    status: Status,
    text: str = "t",
    page: int | None = None,
    evidence: tuple[Evidence, ...] = (),
) -> Signal:
    return Signal(
        check="vendor",
        rule=rule,
        subject="V",
        status=status,
        text=text,
        page=page,
        evidence=evidence,
    )


def test_the_letter_uses_only_mismatches_and_carries_page_and_source() -> None:
    card = build_card(
        "q1", "DEMO LIMITED",
        [sig("VX-02", Status.CONSISTENT, "fine line"), sig("VX-03", Status.INCONSISTENT, "quote is 1,770 times capital", page=89, evidence=(PROOF,))],
    )  # fmt: skip
    letter = draft_comment(card)
    assert letter is not None
    assert "quote is 1,770 times capital" in letter
    assert "fine line" not in letter
    assert "page 89" in letter
    assert "https://www.instafinancials.com/company/x" in letter
    assert "SerpApi search id abc123" in letter


def test_the_letter_is_neutral_and_says_it_alleges_nothing() -> None:
    card = build_card(
        "q1",
        "DEMO LIMITED",
        [sig("VX-03", Status.INCONSISTENT, "worth a closer look", evidence=(PROOF,))],
    )
    letter = draft_comment(card) or ""
    assert banned_terms(letter) == []
    assert "not allegations" in letter
    assert "makes no claim of wrongdoing" in letter
    assert "[your name]" in letter


def test_no_mismatches_means_no_letter() -> None:
    card = build_card(
        "q1", "DEMO LIMITED", [sig("VX-02", Status.CONSISTENT), sig("VX-05", Status.UNVERIFIED)]
    )
    assert draft_comment(card) is None


def test_personal_identifiers_never_reach_the_letter() -> None:
    card = build_card(
        "q1",
        "DEMO LIMITED",
        [sig("LT-03", Status.INCONSISTENT, "matter naming PAN ABCDE1234F of a promoter")],
    )
    assert "ABCDE1234F" not in (draft_comment(card) or "")
