# company names normalized for matching registry rows, maps places and order pages
import re
import unicodedata

from rapidfuzz import fuzz

# legal forms say nothing about which company it is, so they drop out before comparing
LEGAL_WORDS = frozenset({"pvt", "private", "ltd", "limited", "llp", "opc", "the"})
NON_WORD = re.compile(r"[^a-z0-9]+")
MS_PREFIX = re.compile(r"^\s*m\s*/\s*s\.?\s*")


def similarity(a: str, b: str) -> float:
    left, right = normalize_company(a), normalize_company(b)
    if not left or not right:
        return 0.0
    return float(fuzz.token_sort_ratio(left, right)) / 100


def normalize_company(name: str) -> str:
    text = unicodedata.normalize("NFKC", name).lower()
    text = MS_PREFIX.sub("", text).replace("&", " and ")
    tokens = [t for t in NON_WORD.sub(" ", text).split() if t not in LEGAL_WORDS]
    return " ".join(join_initials(tokens))


def join_initials(tokens: list[str]) -> list[str]:
    # "i t s" written as I.T.S. should read the same as "its"
    out: list[str] = []
    run = ""
    for token in tokens:
        if len(token) == 1 and token.isalpha():
            run += token
            continue
        if run:
            out.append(run)
            run = ""
        out.append(token)
    if run:
        out.append(run)
    return out
