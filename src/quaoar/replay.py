# replay bundles: a finished scan's events and card, scrubbed, so anyone can watch it with no keys
import json
from collections.abc import Callable
from pathlib import Path

from quaoar.events import Event
from quaoar.guard.hits import Cleaned
from quaoar.guard.pii import mask_pii
from quaoar.guard.secrets import SecretRedactor
from quaoar.guard.text import clean_text
from quaoar.scoring.card import Card

EVENTS = "events.jsonl"
CARD = "card.json"


class ReplayBundleError(ValueError):
    pass


def export_scan(scan_dir: Path, dest: Path, secrets: list[str]) -> Path:
    events, card = scan_dir / EVENTS, scan_dir / CARD
    if not events.is_file() or not card.is_file():
        raise ReplayBundleError(f"{scan_dir} has no finished scan")
    redact = SecretRedactor(secrets).redact

    # every line is cleaned, masked and redacted, then re-validated before it is written
    dest.mkdir(parents=True, exist_ok=True)
    lines = [
        scrub(line, redact)
        for line in events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for line in lines:
        Event.model_validate_json(line)
    (dest / EVENTS).write_text("\n".join(lines) + "\n", encoding="utf-8")
    clean_card = Card.model_validate_json(scrub(card.read_text(encoding="utf-8"), redact))
    (dest / CARD).write_text(clean_card.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return dest


def load_replay(bundle: Path) -> tuple[list[Event], Card]:
    try:
        lines = (bundle / EVENTS).read_text(encoding="utf-8").splitlines()
        card = Card.model_validate_json((bundle / CARD).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReplayBundleError(f"unreadable replay bundle {bundle.name}") from exc
    return [Event.model_validate_json(line) for line in lines if line.strip()], card


def scrub(text: str, redact: Callable[[str], Cleaned]) -> str:
    cleaned = mask_pii(redact(clean_text(text).text).text).text
    json.loads(cleaned)  # still one valid json document after scrubbing
    return cleaned
