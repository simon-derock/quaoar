# G1 text hygiene: untrusted strings lose escape codes, controls and bidi tricks first
import re
import unicodedata

from quaoar.guard.hits import Cleaned, GuardHit

# OSC goes before CSI because both start with ESC
OSC = r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
CSI = r"\x1b\[[0-?]*[ -/]*[@-~]"
# C0/C1 controls except tab and newline, bidi overrides and isolates, zero-width marks
INVISIBLE = r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069\u200b-\u200d\ufeff]"
UNSAFE = re.compile(f"{OSC}|{CSI}|{INVISIBLE}")


def clean_text(text: str) -> Cleaned:
    stripped, removed = UNSAFE.subn("", text)
    normal = unicodedata.normalize("NFKC", stripped)
    hits = (GuardHit("G1", "unsafe_chars", removed),) if removed else ()
    return Cleaned(normal, hits)
