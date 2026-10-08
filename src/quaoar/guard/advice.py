# G8 advice intent: questions about buying or price get facts and a plain disclaimer
import re

from quaoar.guard.hits import GuardHit

ADVICE_REPLY = "Quaoar doesn't give investment advice. Here is what the public record shows."

ADVICE = re.compile(
    r"\bshould\s+i\s+(?:buy|apply|sell|invest|subscribe|hold|exit)\b"
    r"|\b(?:target|fair)\s+price\b"
    r"|\bwill\s+(?:it|this|the\s+(?:stock|share|ipo))\s+"
    r"(?:go\s+up|rise|fall|list\s+(?:high|at\s+a\s+premium))\b"
    r"|\bmultibagger\b|\blisting\s+gains?\b"
    r"|\bkya\s+(?:main|mai|mein)\s+(?:apply|invest|kharid)\w*"
    r"|\b(?:kharidu|kharidun|bechu|bechun)\b",
    re.I,
)


def advice_request(text: str) -> GuardHit | None:
    count = len(ADVICE.findall(text))
    return GuardHit("G8", "advice_request", count) if count else None
