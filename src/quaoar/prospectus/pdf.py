# page text from untrusted pdfs, parsed in an isolated child interpreter with hard limits
import json
import subprocess  # nosec B404: fixed argv, no shell, see read_pages
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_PAGES = 800
WALL_SECONDS = 60.0
MIN_TEXT_CHARS = 30


class PdfParseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Page:
    number: int
    text: str
    needs_ocr: bool


def read_pages(
    path: Path, max_pages: int = MAX_PAGES, timeout_s: float = WALL_SECONDS
) -> list[Page]:
    # -I keeps the child free of PYTHON* env vars, user site and the current directory
    argv = [sys.executable, "-I", "-m", "quaoar.prospectus.pdfworker", str(path), str(max_pages)]
    try:
        done = subprocess.run(argv, capture_output=True, timeout=timeout_s, check=False)  # noqa: S603  # nosec B603
    except subprocess.TimeoutExpired as exc:
        raise PdfParseError(f"parse took longer than {timeout_s} s, time limit hit") from exc

    try:
        result = json.loads(done.stdout)
    except ValueError as exc:
        raise PdfParseError(f"parser process died (exit {done.returncode})") from exc
    if not result.get("ok"):
        raise PdfParseError(str(result.get("error", "unknown parser error")))
    return [Page(n, text, len(text.strip()) < MIN_TEXT_CHARS) for n, text in result["pages"]]
