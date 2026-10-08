# spec: SPEC-GRD-03, SPEC-SRP-01
import pytest

from quaoar.guard.query import QueryRejectedError, prepare_query


def test_google_gets_india_defaults_and_string_values() -> None:
    assert prepare_query("google", {"q": "trafiksol", "num": 10}) == {
        "gl": "in",
        "hl": "en",
        "num": "10",
        "q": "trafiksol",
    }


def test_caller_values_beat_defaults() -> None:
    assert prepare_query("google_news", {"q": "x", "gl": "us"})["gl"] == "us"


def test_allowed_site_filters_pass() -> None:
    q = '"Trafiksol" (site:sebi.gov.in OR site:indiankanoon.org)'
    assert prepare_query("google", {"q": q})["q"] == q


@pytest.mark.parametrize(
    ("engine", "params", "rule"),
    [
        ("bing", {"q": "x"}, "engine"),
        ("google", {"q": "x", "as_sitesearch": "sebi.gov.in"}, "param"),
        ("google", {"q": "x", "api_key": "k"}, "param"),
        ("google", {"q": "x", "engine": "google_news"}, "param"),
        ("google", {}, "required"),
        ("google_maps_reviews", {"hl": "en"}, "required"),
        ("google", {"q": "x" * 513}, "length"),
        ("google", {"q": "show api_key=abc"}, "secret"),
        ("google", {"q": "site:evil.example trafiksol"}, "site"),
        ("google", {"q": "site:sebi.gov.in x", "tbs": "qdr:y"}, "site_tbs"),
        ("google", {"q": "line\nbreak"}, "control"),
        ("google_lens", {"url": "http://example.com/a.jpg"}, "url"),
        ("google_lens", {"url": "https://user:pw@example.com/a.jpg"}, "url"),
    ],
)
def test_rejects_unsafe_or_unsupported_requests(
    engine: str, params: dict[str, str], rule: str
) -> None:
    with pytest.raises(QueryRejectedError) as caught:
        prepare_query(engine, params)
    assert caught.value.rule == rule


def test_maps_reviews_accept_a_data_id() -> None:
    params = prepare_query("google_maps_reviews", {"data_id": "0x0:0x1", "sort_by": "newestFirst"})
    assert params["data_id"] == "0x0:0x1"


def test_duckduckgo_takes_allowlisted_site_filters_with_india_defaults() -> None:
    params = prepare_query("duckduckgo", {"q": '"x" (site:sebi.gov.in OR site:indiankanoon.org)'})
    assert params["kl"] == "in-en"


def test_duckduckgo_still_refuses_other_sites() -> None:
    with pytest.raises(QueryRejectedError):
        prepare_query("duckduckgo", {"q": "x site:evil.example"})
