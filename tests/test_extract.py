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
