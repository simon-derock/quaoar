# spec: SPEC-GRD-04, SPEC-SAF-04
import pytest

from quaoar.guard.pii import mask_pii, verhoeff_check_digit, verhoeff_valid


def test_verhoeff_matches_the_textbook_vector() -> None:
    assert verhoeff_check_digit("236") == "3"
    assert verhoeff_valid("2363")
    assert not verhoeff_valid("2364")


def test_masks_a_checksum_valid_aadhaar_only() -> None:
    body = "23456789012"
    valid = body + verhoeff_check_digit(body)
    invalid = body + str((int(verhoeff_check_digit(body)) + 1) % 10)
    assert mask_pii(f"uid {valid[:4]} {valid[4:8]} {valid[8:]}").text == "uid [aadhaar]"
    assert mask_pii(f"ref {invalid}").text == f"ref {invalid}"


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("PAN: ABCDE1234F of the promoter", "PAN: [pan] of the promoter"),
        ("call +91 98765 43210 now", "call [phone] now"),
        ("mobile 9876543210.", "mobile [phone]."),
        ("write to some.person@gmail.com today", "write to [email] today"),
        ("Flat No. 402, Sunrise Towers, Andheri", "[house no.], Sunrise Towers, Andheri"),
        ("H.No. 12-3/A, Gandhi Nagar", "[house no.], Gandhi Nagar"),
    ],
)
def test_masks_personal_identifiers(raw: str, masked: str) -> None:
    assert mask_pii(raw).text == masked


@pytest.mark.parametrize(
    "text",
    [
        "CIN U72300KA2012PTC066088",
        "issue size Rs. 44.87 crore on 2024-09-10",
        "investor.relations@trafiksol.com",
        "listed on 12.03.2024 with 345.65 times subscription",
    ],
)
def test_company_identifiers_and_numbers_stay(text: str) -> None:
    assert mask_pii(text).text == text
