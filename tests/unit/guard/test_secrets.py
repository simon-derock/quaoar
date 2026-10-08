# spec: SPEC-GRD-05, SPEC-SAF-03
from quaoar.guard.secrets import SecretRedactor

SERP_KEY = "f" * 64
COHERE_KEY = "Ab3" * 13 + "x"


def test_redacts_exact_configured_keys_anywhere() -> None:
    redactor = SecretRedactor([SERP_KEY, COHERE_KEY])
    out = redactor.redact(f"key {SERP_KEY} and {COHERE_KEY}.")
    assert out.text == "key [redacted] and [redacted]."
    assert out.hits[0].count == 2


def test_redacts_api_key_params_and_bearer_tokens_without_known_values() -> None:
    redactor = SecretRedactor([])
    url = "https://serpapi.com/search.json?engine=google&api_key=abc123secret&q=x"
    assert redactor.redact(url).text.endswith("api_key=[redacted]&q=x")
    assert (
        redactor.redact("Authorization: Bearer abcdefgh12345").text
        == "Authorization: Bearer [redacted]"
    )


def test_our_own_sha256_hashes_are_left_alone() -> None:
    digest = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert SecretRedactor([SERP_KEY]).redact(digest).text == digest


def test_short_values_are_never_treated_as_secrets() -> None:
    assert SecretRedactor(["", "abc"]).redact("abc").text == "abc"
