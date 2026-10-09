# health check: are the keys valid, the model reachable and the ledger intact; costs no search credits
import httpx

from quaoar.serp.client import account_lookup
from quaoar.serp.keys import fingerprint
from quaoar.service import Runtime

COHERE_MODELS_URL = "https://api.cohere.com/v1/models"


def diagnose(runtime: Runtime) -> list[tuple[bool, str]]:
    settings, http = runtime.settings, runtime.http
    rows: list[tuple[bool, str]] = []

    lookup = account_lookup(http)
    if not settings.serpapi_keys:
        rows.append((False, "no SerpApi key: set SERPAPI_API_KEYS in .env"))
    for key in settings.serpapi_keys:
        fp = fingerprint(key.get_secret_value())
        try:
            rows.append((True, f"SerpApi key {fp}: {lookup(key.get_secret_value())} searches left"))
        except (httpx.HTTPError, ValueError, KeyError):
            rows.append((False, f"SerpApi key {fp}: rejected or unreachable"))

    if not settings.cohere_keys:
        rows.append((False, "no Cohere key: set COHERE_API_KEYS in .env"))
    rows.extend(
        cohere_row(http, k.get_secret_value(), settings.cohere_model) for k in settings.cohere_keys
    )

    bad = runtime.ledger.blobs.verify_all()
    rows.append(
        (
            not bad,
            "ledger: every stored response matches its hash"
            if not bad
            else f"ledger: {len(bad)} blobs failed their hash",
        )
    )
    return rows


def cohere_row(http: httpx.Client, key: str, model: str) -> tuple[bool, str]:
    fp = fingerprint(key)
    try:
        response = http.get(
            COHERE_MODELS_URL,
            params={"endpoint": "chat", "page_size": 100},
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )
        response.raise_for_status()
        names = {m.get("name") for m in response.json().get("models", [])}
    except (httpx.HTTPError, ValueError):
        return False, f"Cohere key {fp}: rejected or unreachable"
    if model not in names:
        return False, f"Cohere key {fp}: valid, but model {model} is not available to it"
    return True, f"Cohere key {fp}: valid, model {model} available"
