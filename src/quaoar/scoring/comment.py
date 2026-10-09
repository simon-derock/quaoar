# a neutral public-comment letter built only from the lines that did not match; the user sends it
from quaoar.domain.findings import Signal
from quaoar.guard.pii import mask_pii
from quaoar.guard.text import clean_text
from quaoar.scoring.card import DISCLAIMER, Card

SNIPPET = 220


def draft_comment(card: Card) -> str | None:
    points = [s for s in card.signals if s.status.value == "inconsistent"]
    if not points:
        return None

    lines = [
        f"Subject: Public comment on the offer document of {card.company}",
        "",
        "To the Listing Department of the SME exchange,",
        "",
        f"I am a member of the public. While reading the offer document of {card.company}, I compared "
        "some of its statements with publicly available sources. The points below did not match what "
        "I found. They are observations from public sources, not allegations, and I ask that they be "
        "examined.",
        "",
    ]
    for number, signal in enumerate(points, start=1):
        lines += point(number, signal)
    lines += [
        "These points come from automated searches by the open-source tool Quaoar and should be "
        "verified against the original documents.",
        f"{DISCLAIMER} This letter makes no claim of wrongdoing by any person.",
        "",
        "Yours faithfully,",
        "[your name]",
    ]
    return "\n".join(lines) + "\n"


def point(number: int, signal: Signal) -> list[str]:
    lines = [f"{number}. {safe(signal.text)}"]
    if signal.page:
        lines.append(f"   Offer document reference: page {signal.page}.")
    for item in signal.evidence[:2]:
        when = f", published {item.published}" if item.published else ""
        lines.append(
            f"   Source: {item.url} ({safe(item.title)[:90]}{when}; SerpApi search id {item.search_id or 'n/a'})."
        )
    lines.append("")
    return lines


def safe(text: str) -> str:
    return mask_pii(clean_text(text).text).text
