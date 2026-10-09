# spec: SPEC-DIFF-01
from quaoar.domain.claims import DisclosedCaseClaim, Grounded, PromoterClaim, QuoteClaim
from quaoar.guard.wording import banned_terms
from quaoar.prospectus.diff import diff_claims


def quote(vendor: str, amount: str, unit: str = "Lakhs", page: int = 10) -> QuoteClaim:
    return QuoteClaim(page=page, vendor=vendor, item="software", amount_text=amount, unit_text=unit)


def test_an_unchanged_claim_set_has_no_changes() -> None:
    claims = {"quotes": [quote("ACME PRIVATE LIMITED", "1,770.00")]}
    assert diff_claims(claims, claims) == []


def test_a_changed_vendor_quotation_amount_is_reported_in_money_terms_not_text() -> None:
    old = {"quotes": [quote("ACME PRIVATE LIMITED", "1,770.00")]}
    new = {"quotes": [quote("Acme Pvt. Ltd.", "17.70", unit="Crore", page=12)]}
    assert diff_claims(old, new) == []
    new2 = {"quotes": [quote("Acme Pvt. Ltd.", "1,200.00", page=12)]}
    (change,) = diff_claims(old, new2)
    assert (change.kind, change.group, change.page_old, change.page_new) == (
        "changed",
        "quotes",
        10,
        12,
    )
    assert "₹17.70 Cr earlier, ₹12.00 Cr later" in change.text


def test_a_swapped_vendor_shows_as_one_removed_and_one_added() -> None:
    old = {"quotes": [quote("ACME PRIVATE LIMITED", "100")]}
    new = {"quotes": [quote("BETA INDUSTRIES LIMITED", "100")]}
    kinds = sorted((c.kind, c.group) for c in diff_claims(old, new))
    assert kinds == [("added", "quotes"), ("removed", "quotes")]


def test_cases_match_by_reference_and_promoters_by_normalized_name() -> None:
    old: dict[str, list[Grounded]] = {
        "cases": [DisclosedCaseClaim(page=5, party="A", case_ref="ZD 0905-24")],
        "promoters": [PromoterClaim(page=3, name="Person One")],
    }
    new: dict[str, list[Grounded]] = {
        "cases": [
            DisclosedCaseClaim(page=6, party="A Ltd", case_ref="zd090524"),
            DisclosedCaseClaim(page=6, party="B", case_ref="X1"),
        ],
        "promoters": [PromoterClaim(page=3, name="person  one")],
    }
    changes = diff_claims(old, new)
    assert [(c.kind, c.group) for c in changes] == [("added", "cases")]


def test_change_text_is_neutral() -> None:
    old = {"quotes": [quote("ACME PRIVATE LIMITED", "100")]}
    for change in diff_claims(old, {"quotes": []}):
        assert banned_terms(change.text) == []
