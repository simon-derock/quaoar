# spec: SPEC-DOM-02
import pytest

from quaoar.domain.names import normalize_company, similarity


@pytest.mark.parametrize(
    ("raw", "normal"),
    [
        ("Oasis Corpcare Pvt. Ltd.", "oasis corpcare"),
        ("OASIS CORPCARE PRIVATE LIMITED", "oasis corpcare"),
        ("M/s. ABC & Co", "abc and co"),
        ("Trafiksol I.T.S. Technologies Limited", "trafiksol its technologies"),
        ("  \uff36\uff41\uff52\uff41\uff4e\uff49\uff55\uff4d   Cloud  Ltd ", "varanium cloud"),
    ],
)
def test_normalizes_case_punctuation_and_legal_suffixes(raw: str, normal: str) -> None:
    assert normalize_company(raw) == normal


def test_same_company_written_differently_scores_one() -> None:
    assert similarity("Oasis Corpcare Pvt. Ltd.", "OASIS CORPCARE PRIVATE LIMITED") == 1.0
    assert similarity("Trafiksol ITS Technologies Ltd", "Trafiksol I.T.S. Technologies") == 1.0


def test_partial_name_is_not_a_match() -> None:
    assert similarity("Oasis Corpcare", "Oasis") < 0.85


def test_different_companies_sharing_a_word_stay_below_the_order_threshold() -> None:
    assert similarity("Kaveri Corporation", "Maruti Corporation") < 0.9


def test_empty_names_never_match() -> None:
    assert similarity("Pvt Ltd", "Private Limited") == 0.0
