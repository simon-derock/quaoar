# spec: SPEC-RT-01, SPEC-CLI-05
from pathlib import Path

import pytest

from quaoar.prospectus.acquire import IntakeError
from quaoar.service import intake, make_runtime, save, scan_folder
from tests.pdfgen import make_pdf


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("QUAOAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SERPAPI_API_KEYS", "")
    return make_runtime(tmp_path / "no.env")


def test_intake_reads_a_local_pdf_and_refuses_junk(runtime, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(make_pdf([["hello world page one text"]]))
    assert intake(str(pdf), runtime).size > 0
    with pytest.raises(IntakeError):
        intake(str(tmp_path / "missing.pdf"), runtime)


def test_urls_to_exchange_hosts_are_refused_before_any_request(runtime) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(IntakeError) as caught:
        intake("https://www.bseindia.com/x.pdf", runtime)
    assert caught.value.rule == "exchange"


def test_scan_folder_lives_under_the_home(runtime) -> None:  # type: ignore[no-untyped-def]
    assert scan_folder(runtime, "q1") == runtime.settings.home / "scans" / "q1"
    assert callable(save)
