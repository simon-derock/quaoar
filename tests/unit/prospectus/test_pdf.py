# spec: SPEC-PDF-02, SPEC-SAF-06
from pathlib import Path

import pytest

from quaoar.prospectus.pdf import PdfParseError, read_pages
from quaoar.prospectus.pdfworker import extract
from tests.pdfgen import make_pdf


def write(tmp_path: Path, pages: list[list[str]]) -> Path:
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_pdf(pages))
    return path


def test_text_comes_back_per_page_with_one_based_numbers(tmp_path: Path) -> None:
    pages = read_pages(
        write(tmp_path, [["OBJECTS OF THE ISSUE", "Software Rs. 17.70 crore"], ["OUR BUSINESS"]])
    )
    assert [p.number for p in pages] == [1, 2]
    assert "Software Rs. 17.70 crore" in pages[0].text
    assert "OUR BUSINESS" in pages[1].text


def test_pages_without_text_are_marked_for_ocr(tmp_path: Path) -> None:
    pages = read_pages(write(tmp_path, [["enough words on this page to count as text"], []]))
    assert [p.needs_ocr for p in pages] == [False, True]


def test_page_cap_stops_huge_documents(tmp_path: Path) -> None:
    pages = read_pages(
        write(tmp_path, [[f"page {i} has plenty of text in it"] for i in range(5)]), max_pages=3
    )
    assert len(pages) == 3


def test_broken_file_fails_cleanly_in_the_child(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not really a pdf")
    with pytest.raises(PdfParseError):
        read_pages(path)


def test_wall_clock_limit_kills_a_stuck_parse(tmp_path: Path) -> None:
    with pytest.raises(PdfParseError, match="time"):
        read_pages(write(tmp_path, [["x" * 40]]), timeout_s=0.0001)


def test_worker_extract_runs_in_process_too(tmp_path: Path) -> None:
    pages = extract(str(write(tmp_path, [["hello from the worker"]])), 10)
    assert pages[0][0] == 1
    assert "hello from the worker" in pages[0][1]
