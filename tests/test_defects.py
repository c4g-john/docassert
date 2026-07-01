"""Tests for the 0.2.1 defect fixes: exit-code cap, --documents-dir, alignment cap."""
from docassert import consistency as C
from docassert.cli import _capped, main
from docassert.graph import Graph
from docassert.models import CheckResult, Item

PROJECT_MD = """---
kind: project
id: PRJ-009-TST
code: TST
name: Test Project
sponsor: jane.doe
status: proposed
---

## Overview
A test project.

## Scope
Everything.
"""


# ── exit-code cap ────────────────────────────────────────────────────────────
def test_exit_code_capped_below_wraparound():
    assert _capped(0) == 0
    assert _capped(3) == 3
    assert _capped(125) == 125
    assert _capped(256) == 125   # would otherwise wrap to exit status 0
    assert _capped(1000) == 125


# ── --documents-dir ──────────────────────────────────────────────────────────
def test_projects_reads_documents_dir_flag(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "elsewhere"
    (docs / "PRJ-009-TST").mkdir(parents=True)
    (docs / "PRJ-009-TST" / "project.md").write_text(PROJECT_MD, encoding="utf-8")
    monkeypatch.chdir(tmp_path)   # cwd has no documents/ at all
    assert main(["projects", "--documents-dir", str(docs)]) == 0
    assert "PRJ-009-TST" in capsys.readouterr().out


def test_status_reads_documents_dir_flag(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "elsewhere"
    (docs / "PRJ-009-TST").mkdir(parents=True)
    (docs / "PRJ-009-TST" / "project.md").write_text(PROJECT_MD, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["status", "--documents-dir", str(docs), "--summary"]) == 0
    assert "Derived from 1 documents" in capsys.readouterr().out


# ── alignment call cap ───────────────────────────────────────────────────────
def _graph_with_edges(n):
    g = Graph()
    g.add(Item("TST-BR-001", "TST", "BR", "parent", {}, "d.md", "k", "approved", "S"))
    for i in range(n):
        g.add(Item(f"TST-PR-{i:03d}", "TST", "PR", "child",
                   {"traces": ["TST-BR-001"]}, "d.md", "k", "approved", "S"))
    return g


def _stub_calls(monkeypatch):
    calls = []
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(C, "run_alignment",
                        lambda cid, *a: calls.append(cid) or CheckResult(
                            cid, True, False, "ok", kind="semantic", score=1.0))
    return calls


def test_alignment_capped(monkeypatch):
    calls = _stub_calls(monkeypatch)
    cfg = {"alignment": [{"relation": "traces", "prompt": "judge"}], "alignment_limit": 2}
    results = C.run_alignment_checks(_graph_with_edges(4), cfg)
    assert len(calls) == 2
    note = next(r for r in results if r.check_id == "alignment-limit")
    assert "graded 2 of 4" in note.detail and not note.blocking


def test_alignment_cap_disabled_with_zero(monkeypatch):
    calls = _stub_calls(monkeypatch)
    cfg = {"alignment": [{"relation": "traces", "prompt": "judge"}], "alignment_limit": 0}
    results = C.run_alignment_checks(_graph_with_edges(4), cfg)
    assert len(calls) == 4
    assert not any(r.check_id == "alignment-limit" for r in results)
