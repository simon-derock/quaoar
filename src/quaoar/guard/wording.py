# G7 wording: user-facing text reports evidence, never accusations or advice
import re

BANNED = (
    "fraud", "fraudulent", "scam", "scamster", "fake", "cheat", "ponzi",
    "buy", "sell", "avoid", "invest now", "multibagger", "sure shot", "guaranteed",
    "target price", "dhokha", "ghotala", "farzi", "nakli", "kharido", "becho",
)  # fmt: skip

# a space inside a term also matches a hyphen, so "sure-shot" is caught too
BANNED_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(t).replace(r"\ ", r"[\s-]+") for t in BANNED) + r")\b",
    re.I,
)


def banned_terms(text: str) -> list[str]:
    found: list[str] = []
    for match in BANNED_PATTERN.finditer(text):
        term = match.group(0).lower()
        if term not in found:
            found.append(term)
    return found
