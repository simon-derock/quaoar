# writes web/primer.json: the website's chat answers, generated from the same rules the cli and api use
import json
import sys
from pathlib import Path

from quaoar.api.app import NO_ADVICE, NOT_UNDERSTOOD
from quaoar.guard.advice import ADVICE
from quaoar.primer import RULES, WEB

OUT = Path(__file__).resolve().parents[1] / "web" / "primer.json"


def export() -> str:
    data = {
        "advice": {"pattern": ADVICE.pattern, "reply": NO_ADVICE},
        "rules": [{"pattern": p.pattern, "reply": WEB.get(reply, reply)} for p, reply in RULES],
        "fallback": NOT_UNDERSTOOD,
    }
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(export(), encoding="utf-8")
    sys.stdout.write(f"wrote {OUT}\n")
