# isolated pdf text worker: run as `python -I -m quaoar.prospectus.pdfworker <path> <max_pages>`
import json
import resource
import sys

CPU_SECONDS = 30
MEMORY_BYTES = 1536 * 1024 * 1024


def main(argv: list[str]) -> int:
    # the limits bind this process only, so a hostile pdf cannot exhaust the parent
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    try:
        pages = extract(argv[1], int(argv[2]))
    except Exception as exc:
        sys.stdout.write(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}))
        return 1
    sys.stdout.write(json.dumps({"ok": True, "pages": pages}))
    return 0


def extract(path: str, max_pages: int) -> list[tuple[int, str]]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(path)
    pages = []
    for index in range(min(len(document), max_pages)):
        text = document[index].get_textpage().get_text_range()
        pages.append((index + 1, text.replace("\r\n", "\n").replace("\r", "\n")))
    return pages


if __name__ == "__main__":
    sys.exit(main(sys.argv))
