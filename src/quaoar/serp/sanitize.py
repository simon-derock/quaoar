# stored responses lose api keys everywhere and reviewer identities entirely
import re

from pydantic import JsonValue

API_KEY_IN_TEXT = re.compile(r"([?&]api_key=)[^&\s\"'#]+", re.I)
REVIEW_FIELDS = frozenset({"rating", "date", "iso_date", "iso_date_of_last_edit"})
REVIEW_CONTAINERS = frozenset({"reviews", "user_reviews"})


def sanitize(engine: str, body: dict[str, JsonValue]) -> dict[str, JsonValue]:
    clean = cleaned(body)
    # only review lists from maps engines carry people; other "reviews" keys are left alone
    if engine.startswith("google_maps") and isinstance(clean, dict):
        return {
            k: prune_reviews(v) if k in REVIEW_CONTAINERS else drill(v) for k, v in clean.items()
        }
    return clean if isinstance(clean, dict) else {}


def cleaned(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {k: cleaned(v) for k, v in value.items() if k.lower() != "api_key"}
    if isinstance(value, list):
        return [cleaned(v) for v in value]
    if isinstance(value, str):
        return API_KEY_IN_TEXT.sub(r"\1[redacted]", value)
    return value


def drill(value: JsonValue) -> JsonValue:
    # place results nest user_reviews one level down
    if isinstance(value, dict):
        return {
            k: prune_reviews(v) if k in REVIEW_CONTAINERS else drill(v) for k, v in value.items()
        }
    return value


def prune_reviews(value: JsonValue) -> JsonValue:
    if isinstance(value, list):
        return [
            {k: v for k, v in item.items() if k in REVIEW_FIELDS}
            if isinstance(item, dict)
            else item
            for item in value
        ]
    if isinstance(value, dict):
        return {k: prune_reviews(v) for k, v in value.items()}
    return value
