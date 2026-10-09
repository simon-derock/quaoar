# spec: SPEC-GRD-01
from quaoar.domain.claims import PlaceClaim, QuoteClaim


def test_names_cut_by_pdf_line_breaks_are_one_clean_line() -> None:
    quote = QuoteClaim(
        page=3,
        vendor="welding ROBOT Systems\nIndia Pvt. \nLtd",
        item="robotic\tcell",
        amount_text="1,00,000",
    )
    assert quote.vendor == "welding ROBOT Systems India Pvt. Ltd"
    assert quote.item == "robotic cell"
    place = PlaceClaim(page=1, role="factory", locality="MIDC\n Miraj", city=" Sangli\n")
    assert (place.locality, place.city) == ("MIDC Miraj", "Sangli")


def test_the_models_own_citation_markup_is_stripped_from_names_and_spans() -> None:
    from quaoar.domain.claims import LeadManagerClaim, PromoterClaim

    lead = LeadManagerClaim(
        page=59,
        name="<co>Getfive Advisors Private Limited</co: 0:[59,62]>",
        span="<co>BOOK RUNNING LEAD MANAGER</co: 0:[1,2]> Getfive",
    )
    assert lead.name == "Getfive Advisors Private Limited"
    assert lead.span == "BOOK RUNNING LEAD MANAGER Getfive"
    assert PromoterClaim(page=1, name="<co>Eldo Varghese</co: 1:[0,3]>, ").name == "Eldo Varghese,"
