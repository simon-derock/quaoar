# spec: SPEC-CLI-01, SPEC-CLI-02, SPEC-CLI-06, SPEC-SAF-08
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quaoar.cli import app, pretty
from quaoar.domain.findings import Signal, Status
from quaoar.events import Event
from quaoar.scoring.card import build_card

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QUAOAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SERPAPI_API_KEYS", "")
    return tmp_path / "home"


def test_help_lists_the_commands() -> None:
    out = runner.invoke(app, ["--help"])
    assert out.exit_code == 0
    for command in ("scan", "card", "ledger", "keys"):
        assert command in out.output


def test_bad_input_exits_with_code_two() -> None:
    out = runner.invoke(app, ["scan", "missing.pdf"])
    assert out.exit_code == 2
    assert "can't use that input" in out.output


def test_saved_card_prints_with_its_disclaimer(isolated_home: Path) -> None:
    signal = Signal(
        check="vendor",
        rule="VX-03",
        subject="V",
        status=Status.INCONSISTENT,
        text="quote is 1,770 times",
    )
    folder = isolated_home / "scans" / "q1"
    folder.mkdir(parents=True)
    (folder / "card.json").write_text(build_card("q1", "DEMO LIMITED", [signal]).model_dump_json())
    out = runner.invoke(app, ["card", "q1"])
    assert out.exit_code == 0
    assert "doesn't match" in out.output
    assert "Not investment advice" in out.output
    assert runner.invoke(app, ["card", "nope"]).exit_code == 2


def test_pretty_lines_escape_markup_from_untrusted_text() -> None:
    event = Event(
        id="s-1",
        parent=None,
        scan="s",
        t_ns=1,
        type="stage",
        data={"name": "vendor", "subject": "[red]X[/red]\x1b[2J"},
    )
    line = pretty(event)
    assert "\\[red]" in line
    assert "\x1b" not in line


def test_diff_needs_two_readable_pdfs(tmp_path: Path) -> None:
    result = runner.invoke(app, ["diff", "missing-a.pdf", "missing-b.pdf"])
    assert result.exit_code == 2
    assert "can't use that input" in result.output


def test_diff_prints_changes_between_two_claim_sets() -> None:
    from quaoar.cli import render_changes
    from quaoar.prospectus.diff import Change

    lines = render_changes(
        [
            Change(
                "changed",
                "quotes",
                "vendor quotation from ACME changed: ₹1.00 Cr earlier, ₹2.00 Cr later",
                10,
                12,
            )
        ]
    )
    assert "changed" in lines[0]
    assert "page 10 → 12" in lines[0]
    assert render_changes([]) == [
        "no differences in vendors, matters, promoters, group companies, places or lead managers"
    ]


def test_scan_refuses_a_document_that_is_not_a_prospectus(tmp_path: Path) -> None:
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(tiny_pdf("Resume of A. Kumar. Skills: Python and Excel. Experience: 3 years."))
    result = runner.invoke(app, ["scan", str(pdf)])
    assert result.exit_code == 2
    assert "look like an IPO prospectus" in " ".join(result.output.split())


def tiny_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out
