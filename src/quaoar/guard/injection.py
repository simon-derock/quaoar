# G2 injection scan: flags instruction-shaped text inside data, never blocks the scan
import re

from quaoar.guard.hits import GuardHit

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous",
        re.compile(
            r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?"
            r"(?:previous|prior|above|earlier|your|these|those|my)\s+"
            r"(?:instructions?|rules?|prompts?|messages?|guidelines?)\b",
            re.I,
        ),
    ),
    (
        "role_switch",
        re.compile(
            r"\byou\s+are\s+now\b|\bdeveloper\s+mode\b|\bjailbreak\b|"
            r"\bact\s+as\s+(?:an?\s+)?(?:ai|assistant|chatbot|dan|evil|unrestricted|system)\b",
            re.I,
        ),
    ),
    ("prompt_probe", re.compile(r"\bsystem\s+prompt\b", re.I)),
    (
        "verdict_steer",
        re.compile(
            r"\bmark\s+(?:all|every)\s+(?:checks?|claims?)\s+(?:as\s+)?"
            r"(?:consistent|verified|true|clean)\b|\bdo\s+not\s+(?:flag|report|mention)\b",
            re.I,
        ),
    ),
    (
        "role_tags",
        re.compile(
            r"</?\s*(?:system|assistant|user|tool)\s*>|\[/?INST\]|\bBEGIN\s+(?:SYSTEM|INSTRUCTIONS)\b",
            re.I,
        ),
    ),
    ("output_steer", re.compile(r"\brespond\s+only\s+with\b", re.I)),
    ("tool_strings", re.compile(r"\b(?:tool_call|function_call)\b", re.I)),
    # long base64-looking runs are how payloads hide from plain-text review
    ("encoded_blob", re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")),
)


def scan_injection(text: str) -> list[GuardHit]:
    hits = []
    for rule, pattern in PATTERNS:
        count = len(pattern.findall(text))
        if count:
            hits.append(GuardHit("G2", rule, count))
    return hits
