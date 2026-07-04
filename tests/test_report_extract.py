"""Coverage for the report renderers, extraction text paths, and the module
entry point — the last stretch to the 85% floor (ENG-US-009)."""
import runpy

import pytest

from docassert import report
from docassert.extract import extract
from docassert.models import CheckResult


def _results():
    return {
        "documents/a.md": [
            CheckResult("frontmatter-schema", True, True, "ok"),
            CheckResult("required-sections", False, True, "missing: Scope"),
            CheckResult("alignment", False, False, "weak link", kind="semantic",
                        score=0.4),
        ],
        "documents/b.md": [CheckResult("unique-id", True, True, "unique")],
    }


def test_markdown_report_carries_verdicts():
    md = report.markdown(_results())
    assert "a.md" in md and "required-sections" in md
    assert "🔴" in md and "🟢" in md and "⚪" not in md.split("alignment")[0]


def test_junit_report_is_valid_xml_with_failures():
    import xml.etree.ElementTree as ET
    xml = report.junit(_results())
    root = ET.fromstring(xml)
    assert root.tag in {"testsuite", "testsuites"}
    assert int(root.get("failures", root.get("errors", "0"))) >= 1 or \
        any(int(s.get("failures", "0")) >= 1 for s in root.iter("testsuite"))


def test_json_console_and_summary_agree_on_failure():
    res = _results()
    assert "1 blocking failure" in report.summary_line(res) \
        or "blocking" in report.summary_line(res)
    assert "required-sections" in report.console(res)
    assert '"passed": false' in report.json_report(res)


def test_extract_reads_md_and_txt(tmp_path):
    md = tmp_path / "s.md"
    md.write_text("# hello", encoding="utf-8")
    txt = tmp_path / "s.txt"
    txt.write_text("plain", encoding="utf-8")
    assert extract(md) == "# hello"
    assert extract(txt) == "plain"


def test_extract_rejects_unknown_and_missing(tmp_path):
    odd = tmp_path / "s.xyz"
    odd.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        extract(odd)
    with pytest.raises(FileNotFoundError):
        extract(tmp_path / "absent.md")


def test_module_entry_point_reports_version(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["docassert", "--version"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("docassert.__main__", run_name="__main__")
    assert exc.value.code == 0
    assert "docassert" in capsys.readouterr().out
