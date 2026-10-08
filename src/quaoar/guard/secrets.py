# G6 secret redaction: exact configured keys plus key-shaped params and bearer tokens
import re
from collections.abc import Iterable

from quaoar.guard.hits import Cleaned, GuardHit

API_KEY_PARAM = re.compile(r"(api_key=)[^&\s\"'<>]+", re.I)
BEARER = re.compile(r"\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.I)
MIN_SECRET_LENGTH = 12
MASK = "[redacted]"


class SecretRedactor:
    def __init__(self, secrets: Iterable[str]) -> None:
        # generic 64-hex is not redacted on purpose: our own evidence hashes look the same
        values = sorted({s for s in secrets if len(s) >= MIN_SECRET_LENGTH}, key=len, reverse=True)
        self._exact = re.compile("|".join(map(re.escape, values))) if values else None

    def redact(self, text: str) -> Cleaned:
        total = 0
        if self._exact is not None:
            text, n = self._exact.subn(MASK, text)
            total += n
        text, n = API_KEY_PARAM.subn(rf"\g<1>{MASK}", text)
        total += n
        text, n = BEARER.subn(rf"\g<1>{MASK}", text)
        total += n
        hits = (GuardHit("G6", "secret", total),) if total else ()
        return Cleaned(text, hits)
