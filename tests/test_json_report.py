"""Tests for the machine-readable JSON report (`--json`)."""
import json
from pathlib import Path

from docassert import report
from docassert.cli import main
from docassert.models import CheckResult

ROOT = Path(__file__).resolve().parent.parent


def test_json_report_shape():
    results = {
        "a.md": [CheckResult("c1", True, True, "ok"),
                 CheckResult("c2", False, True, "bad")],
        "b.md": [CheckResult("c3", False, False, "meh", kind="semantic", score=0.4)],
    }
    data = json.loads(report.json_report(results))
    assert data["summary"] == {"documents": 2, "checks": 3, "blocking_failures": 1,
                               "advisory_failures": 1, "passed": False}
    assert data["documents"]["a.md"][1]["check_id"] == "c2"
    assert data["documents"]["b.md"][0]["score"] == 0.4


def test_cli_validate_writes_json(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)  # criteria/schema resolve; sample documents exist
    out = tmp_path / "r.json"
    code = main(["validate", "documents/PRJ-001-AUR/charter.md", "--json", str(out)])
    assert code == 0
    data = json.loads(out.read_text())
    assert data["summary"]["passed"] is True
    assert "documents/PRJ-001-AUR/charter.md" in data["documents"]


def test_cli_consistency_writes_json(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "c.json"
    code = main(["consistency", "--no-semantic", "--json", str(out)])
    assert code == 0
    data = json.loads(out.read_text())
    checks = {c["check_id"] for c in data["documents"]["consistency (cross-document)"]}
    assert {"item-id-uniqueness", "referential-integrity", "coverage"} <= checks
