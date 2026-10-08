# spec: SPEC-VX-02, SPEC-SRP-05
from datetime import date

from quaoar.checks.registry import is_registry_url, read_facts, registry_core

INSTA = {
    "title": "Oasis corpcare private limited - U74120MH2013PTC240744",
    "link": "https://www.instafinancials.com/company/oasis-corpcare-private-limited-U74120MH2013PTC240744",
    "snippet": (
        "OASIS CORPCARE PRIVATE LIMITED is a 12.7 Years old company, incorporated on 26 Feb 2013. "
        "The current status of the company is Active. It is classified as Private UnListed Indian "
        "Non-Government Company. Its authorized share capital is ₹1,00,000.00 ( ₹1.00 Lakhs ) and its "
        "paid up capital is ₹1,00,000.00 ( ₹1.00 Lakhs ) As per MCA the main line of business is "
        "Other Business Activities."
    ),
}
ZAUBA = {
    "title": "OASIS CORPCARE PRIVATE LIMITED - ZaubaCorp",
    "link": "https://www.zaubacorp.com/company/OASIS-CORPCARE-PRIVATE-LIMITED/U74120MH2013PTC240744",
    "snippet": "OASIS CORPCARE is a 12 year old company with registered office in Mumbai, Maharashtra.",
}
ELSEWHERE = {
    "title": "Oasis Corpcare Private Limited",
    "link": "https://in.linkedin.com/company/oasis",
    "snippet": "paid up capital is ₹99,00,00,000.00",
}
OTHER_COMPANY = {
    "title": "OASIS CORPORATION LIMITED - ZaubaCorp",
    "link": "https://www.zaubacorp.com/company/OASIS-CORPORATION/U00000MH2000PLC000000",
    "snippet": "paid up capital is ₹5,00,00,000.00",
}


def test_reads_capital_status_dates_and_cin_from_registry_snippets() -> None:
    facts = read_facts("OASIS CORPCARE PRIVATE LIMITED", [ZAUBA, INSTA])
    assert facts.cin == "U74120MH2013PTC240744"
    assert facts.incorporated == date(2013, 2, 26)
    assert facts.status == "active"
    assert facts.authorised_paise == 1_00_000_00
    assert facts.paid_up_paise == 1_00_000_00
    assert facts.business_line == "Other Business Activities"
    assert len(facts.matched_urls) == 2
    assert facts.city == "Mumbai"


def test_results_off_the_registry_sites_or_for_another_company_are_ignored() -> None:
    facts = read_facts("OASIS CORPCARE PRIVATE LIMITED", [ELSEWHERE, OTHER_COMPANY])
    assert facts.paid_up_paise is None
    assert facts.matched_urls == []


def test_staleness_dates_are_read_when_present() -> None:
    snippet = dict(
        INSTA, snippet="Last AGM was held on 30 Sep 2019 and balance sheet as on 31 March 2019."
    )
    facts = read_facts("Oasis Corpcare Pvt Ltd", [snippet])
    assert facts.last_agm == date(2019, 9, 30)
    assert facts.last_balance_sheet == date(2019, 3, 31)


def test_query_core_and_domain_filter() -> None:
    assert registry_core("OASIS CORPCARE PRIVATE LIMITED") == "OASIS CORPCARE"
    assert is_registry_url("https://www.tofler.in/x")
    assert not is_registry_url("https://tofler.in.evil.example/x")
