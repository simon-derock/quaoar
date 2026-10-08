# spec: SPEC-SAN-01, SPEC-SAN-02
from pydantic import JsonValue

from quaoar.serp.sanitize import sanitize


def test_api_key_disappears_from_keys_urls_and_nested_values() -> None:
    body: dict[str, JsonValue] = {
        "search_metadata": {
            "id": "sid",
            "json_endpoint": "https://serpapi.com/searches/sid.json?api_key=SECRET1&x=1",
        },
        "search_parameters": {"engine": "google", "api_key": "SECRET2"},
        "pages": ["https://serpapi.com/search?q=a&api_key=SECRET3"],
    }
    clean = sanitize("google", body)
    text = str(clean)
    assert "SECRET" not in text
    assert "api_key=[redacted]&x=1" in text
    assert clean["search_parameters"] == {"engine": "google"}


def test_maps_reviews_keep_only_rating_and_dates() -> None:
    body: dict[str, JsonValue] = {
        "place_info": {"title": "Oasis Corpcare", "rating": 4.1},
        "reviews": [
            {
                "rating": 5,
                "iso_date": "2019-03-01T10:00:00Z",
                "date": "6 years ago",
                "user": {"name": "A Person", "link": "https://maps.example/u/1"},
                "snippet": "great service",
                "images": ["https://img.example/1.jpg"],
            }
        ],
    }
    clean = sanitize("google_maps_reviews", body)
    assert clean["reviews"] == [
        {"rating": 5, "iso_date": "2019-03-01T10:00:00Z", "date": "6 years ago"}
    ]
    assert clean["place_info"] == {"title": "Oasis Corpcare", "rating": 4.1}


def test_user_reviews_inside_a_place_result_are_pruned_too() -> None:
    body: dict[str, JsonValue] = {
        "place_results": {
            "title": "X",
            "user_reviews": {"most_relevant": [{"username": "u", "rating": 3}]},
        }
    }
    clean = sanitize("google_maps", body)
    assert clean["place_results"] == {
        "title": "X",
        "user_reviews": {"most_relevant": [{"rating": 3}]},
    }


def test_input_is_not_mutated() -> None:
    body: dict[str, JsonValue] = {"search_parameters": {"api_key": "K"}}
    sanitize("google", body)
    assert body == {"search_parameters": {"api_key": "K"}}
