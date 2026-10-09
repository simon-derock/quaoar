# plain answers for people new to IPOs; fixed text, no model, so it works offline and never drifts into a view
import re

INTRO = (
    "Quaoar checks an SME IPO before you apply. Give it the company's prospectus (a PDF) and it "
    "checks what the document claims (its vendors, offices, lead manager, court cases) against "
    "public search results. You get a list of what checks out, what doesn't match and what it "
    "couldn't find, each with a source link. It gives no view on whether to apply.\n"
    "Try: /replay trafiksol (a recorded case, no keys needed), or type the path of a prospectus PDF."
)
SME = (
    "An SME IPO is a small company selling shares to the public for the first time, listed on "
    "NSE Emerge or the BSE SME platform. These companies are often little known and have less "
    "public information, and applications are in lots that cost a lakh or more. That is why it "
    "helps to check what the prospectus says before you apply."
)
PROSPECTUS = (
    "A prospectus is the legal document a company files to sell shares. The draft (DRHP) is "
    "public for comment, the red herring (RHP) is what investors see while the issue is open, and "
    "the final prospectus is filed after bidding closes. To check before you apply, use the RHP."
)
WHERE = (
    "Download the prospectus from the website of the lead manager (the merchant banker named on "
    "its cover) or from SEBI's filings page. NSE and BSE forbid automated downloads, so Quaoar "
    "refuses their links: save the PDF yourself and type its path, for example "
    "/scan ~/Downloads/rhp.pdf. Quaoar reads the document, so it cannot check a company from "
    "its name alone."
)
HOW = (
    "1. Download the prospectus PDF (ask me where).\n"
    "2. Type its path, or /scan <path>. A live scan uses SerpApi credits; /budget caps them.\n"
    "3. Read the card, then /proof <line> shows the page and source behind any line.\n"
    "To see a finished example first: /replay trafiksol."
)
STATUSES = (
    "checks out: public evidence agrees with the document.\n"
    "doesn't match: public evidence disagrees with the document; the source is shown. It is a "
    "reason to look closer, not a verdict.\n"
    "couldn't find: no public evidence turned up. Small private firms often barely appear online, "
    "so this is common and is never counted against a company."
)
VERDICT = (
    "Quaoar doesn't say whether an IPO is safe, good or worth applying to, and gives no advice. "
    "It checks the claims in the prospectus and shows the evidence.\n"
    "Give me the prospectus PDF, or try /replay trafiksol to see what a check looks like."
)
THANKS = "You're welcome. Facts with sources. Not investment advice."

# the web page has no terminal, so the answers that name commands get a version without them
WEB: dict[str, str] = {
    INTRO: INTRO.rsplit("\n", 1)[0]
    + "\nPick a recorded case above to watch a check, or ask me anything about SME IPOs.",
    WHERE: (
        "Download the prospectus from the website of the lead manager (the merchant banker named "
        "on its cover) or from SEBI's filings page. NSE and BSE forbid automated downloads, so "
        "save the PDF yourself. To check one, run Quaoar from your terminal (the steps are in the "
        "GitHub README); this page only replays recorded cases."
    ),
    HOW: (
        "1. Download the prospectus PDF (ask me where).\n"
        "2. Run Quaoar on it from your terminal; a live scan uses SerpApi credits.\n"
        "3. Read the card: every line links to the page and source behind it.\n"
        "To see a finished example first, pick a recorded case above."
    ),
    VERDICT: VERDICT.rsplit("\n", 1)[0]
    + "\nPick a recorded case above to see what a check looks like.",
}

RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.I), reply)
    for pattern, reply in (
        (r"\b(?:thanks|thank\s+you|thx|shukriya|dhanyavad)\b", THANKS),
        (
            r"\b(?:is|are|was|kya)\b.*\b(?:safe|legit|genuine|trustworthy|reliable|good|worth)\b"
            r"|\b(?:safe|legit|genuine)\s*\?",
            VERDICT,
        ),
        (
            r"(?:couldn'?t|could\s+not)\s+find|doesn'?t\s+match|does\s+not\s+match|checks?\s+out",
            STATUSES,
        ),
        (
            r"(?=.*\b(?:where|kahan|kahaan)\b)(?=.*\b(?:get|find|download|prospectus|pdf|milega|milta)\b)",
            WHERE,
        ),
        (r"^\W*(?:please\s+)?(?:can\s+you\s+)?(?:check|scan|analy[sz]e|verify)\b", WHERE),
        (r"\bsme\b.*\b(?:what|kya|explain|mean)\b|\b(?:what|explain)\b.*\bsme\b", SME),
        (
            r"\b(?:what|kya|explain|difference)\b.*\b(?:prospectus|drhp|rhp|red\s+herring)\b",
            PROSPECTUS,
        ),
        (r"\bhow\b.*\b(?:check|use|work|start|begin)\b|\bkaise\b|\bsteps?\b", HOW),
        (
            r"^\W*(?:hi+|hello|hey|namaste)\b|what\s+is\s+this|who\s+are\s+you|what\s+(?:is|does)\s+quaoar"
            r"|know\s+nothing|help\s+me|beginner|new\s+to|\bkya\s+hai\b|\bmadad\b|nahi\s+pata|kuch\s+nahi|samajh\s+nahi|what\s+can\s+you\s+do",
            INTRO,
        ),
    )
)


def answer(text: str, *, web: bool = False) -> str | None:
    if text.startswith("/"):
        return None
    for pattern, reply in RULES:
        if pattern.search(text):
            return WEB.get(reply, reply) if web else reply
    return None
