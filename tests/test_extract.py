"""Tests for the extract module and the `docassert extract` command."""
import pytest

from docassert import extract as E
from docassert.cli import main


# ── the extract() function ──────────────────────────────────────────────────
def test_extract_md(tmp_path):
    f = tmp_path / "s.md"
    f.write_text("# Hello\nworld", encoding="utf-8")
    assert E.extract(f) == "# Hello\nworld"


def test_extract_txt(tmp_path):
    f = tmp_path / "s.txt"
    f.write_text("plain text", encoding="utf-8")
    assert E.extract(str(f)) == "plain text"


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        E.extract(tmp_path / "nope.md")


def test_unsupported_type_raises(tmp_path):
    f = tmp_path / "s.rtf"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        E.extract(f)


def _minimal_pdf(text: str) -> bytes:
    """Assemble a one-page PDF with `text` in a content stream, xref included."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
         b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n").encode()
    return out


def test_extract_pdf(tmp_path):
    pytest.importorskip("pypdf")  # needs the 'convert' extra
    path = tmp_path / "s.pdf"
    path.write_bytes(_minimal_pdf("Hello docassert PDF"))
    assert "Hello docassert PDF" in E.extract(path)


def test_extract_docx_paragraphs_and_tables(tmp_path):
    docx = pytest.importorskip("docx")  # needs the 'convert' extra
    d = docx.Document()
    d.add_paragraph("First para.")
    table = d.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Milestone"
    table.rows[0].cells[1].text = "2026-09-30"
    path = tmp_path / "s.docx"
    d.save(str(path))
    text = E.extract(path)
    assert "First para." in text
    assert "Milestone | 2026-09-30" in text  # table cells joined


# ── the CLI command ─────────────────────────────────────────────────────────
def test_cli_extract_stdout(tmp_path, capsys):
    f = tmp_path / "s.md"
    f.write_text("hello cli", encoding="utf-8")
    assert main(["extract", str(f)]) == 0
    assert "hello cli" in capsys.readouterr().out


def test_cli_extract_out_file(tmp_path):
    src = tmp_path / "s.txt"
    src.write_text("abc", encoding="utf-8")
    out = tmp_path / "out.txt"
    assert main(["extract", str(src), "--out", str(out)]) == 0
    assert out.read_text() == "abc"


def test_cli_extract_missing_returns_2(tmp_path, capsys):
    assert main(["extract", str(tmp_path / "nope.md")]) == 2
    assert "no such file" in capsys.readouterr().err
