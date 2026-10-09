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
