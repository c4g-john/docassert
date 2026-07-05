"""Tests for `docassert new` (docassert/scaffold.py)."""
import datetime as dt

import pytest

from docassert import scaffold
from docassert.cli import main
from docassert.loader import load

BRD_MD = """---
kind: brd
id: AAA-brd
project: PRJ-001-AAA
title: T
owner: o.owner
status: draft
---

## Purpose
p.

## Business Requirements
- **AAA-BR-001**: The business shall do a thing by 2 days.
- **AAA-BR-002**: The business shall do another thing by 3 days.

## Out of Scope
n/a
"""


def _anchor(docs, pid="PRJ-001-AAA", code="AAA"):
    d = docs / pid
    d.mkdir(parents=True)
    (d / "project.md").write_text(f"""---
kind: project
id: {pid}
code: {code}
name: Test
sponsor: s.person
status: proposed
---

## Overview
o.

## Scope
s.
""", encoding="utf-8")


# ── new <kind> into an anchored project ──────────────────────────────────────
def test_new_charter_fills_identity(tmp_path):
    docs = tmp_path / "documents"
    _anchor(docs)
    dest, _ = scaffold.new_document("charter", docs, project="PRJ-001-AAA")
    assert dest == docs / "PRJ-001-AAA" / "charter.md"
    doc = load(dest)
    assert doc.frontmatter["kind"] == "charter"
    assert doc.frontmatter["project"] == "PRJ-001-AAA"
    assert doc.frontmatter["id"] == "AAA-charter"


def test_new_status_report_dated(tmp_path):
    docs = tmp_path / "documents"
    _anchor(docs)
    today = dt.date.today().isoformat()
    dest, _ = scaffold.new_document("status-report", docs, project="PRJ-001-AAA")
    assert dest == docs / "PRJ-001-AAA" / "status-reports" / f"{today}.md"
    fm = load(dest).frontmatter
    assert fm["id"] == f"AAA-status-{today}" and str(fm["period"]) == today


def test_new_without_anchor_notes_it(tmp_path):
    docs = tmp_path / "documents"
    docs.mkdir()
    dest, notes = scaffold.new_document("charter", docs, project="PRJ-002-BBB")
    assert load(dest).frontmatter["id"] == "BBB-charter"
    assert any("no project.md anchor" in n for n in notes)


def test_new_suggests_next_item_ids(tmp_path):
    docs = tmp_path / "documents"
    _anchor(docs)
    (docs / "PRJ-001-AAA" / "brd.md").write_text(BRD_MD, encoding="utf-8")
    _, notes = scaffold.new_document("prd", docs, project="PRJ-001-AAA")
    joined = " ".join(notes)
    assert "AAA-PR-001" in joined and "AAA-AC-001" in joined
    # with the brd (and its items) gone, the BR counter resets
    (docs / "PRJ-001-AAA" / "brd.md").unlink()
    _, notes2 = scaffold.new_document("brd", docs, project="PRJ-001-AAA",
                                      out=tmp_path / "brd2.md")
    assert any("AAA-BR-001" in n for n in notes2)


def test_new_brd_counts_existing_items(tmp_path):
    docs = tmp_path / "documents"
    _anchor(docs)
    (docs / "PRJ-001-AAA" / "brd.md").write_text(BRD_MD, encoding="utf-8")
    _, notes = scaffold.new_document("brd", docs, project="PRJ-001-AAA",
                                     out=tmp_path / "brd2.md")
    assert any("AAA-BR-003" in n for n in notes)


# ── new project ──────────────────────────────────────────────────────────────
def test_new_project_auto_numbers(tmp_path):
    docs = tmp_path / "documents"
    _anchor(docs, "PRJ-001-AAA", "AAA")
    dest, _ = scaffold.new_document("project", docs, code="BBB", name="Bravo")
    assert dest == docs / "PRJ-002-BBB" / "project.md"
    fm = load(dest).frontmatter
    assert fm["id"] == "PRJ-002-BBB" and fm["code"] == "BBB" and fm["name"] == "Bravo"


def test_new_project_rejects_duplicate_code(tmp_path):
    docs = tmp_path / "documents"
    _anchor(docs, "PRJ-001-AAA", "AAA")
    with pytest.raises(ValueError, match="already taken"):
        scaffold.new_document("project", docs, code="AAA")


# ── guardrails ───────────────────────────────────────────────────────────────
def test_unknown_kind_lists_available(tmp_path):
    with pytest.raises(ValueError, match="charter"):
        scaffold.new_document("nope", tmp_path)


def test_refuses_overwrite(tmp_path):
    docs = tmp_path / "documents"
    _anchor(docs)
    scaffold.new_document("charter", docs, project="PRJ-001-AAA")
    with pytest.raises(FileExistsError):
        scaffold.new_document("charter", docs, project="PRJ-001-AAA")


def test_cli_new_missing_project_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["new", "charter"]) == 2
    assert "needs --project" in capsys.readouterr().err


def test_cli_new_creates_and_hints(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "documents"
    _anchor(docs)
    monkeypatch.chdir(tmp_path)
    assert main(["new", "brd", "--project", "PRJ-001-AAA"]) == 0
    out = capsys.readouterr().out
    assert "created" in out and "AAA-BR-001" in out


# ── the adopter path: fresh scaffolds must pass validation ───────────────────
def test_fresh_scaffold_passes_validate(tmp_path, monkeypatch):
    """The template README's first commands: new project, new charter,
    validate. A fresh scaffold failing its own structural gate was a real
    day-one failure (found 2026-07-05 exercising the adopter path); every
    packaged template's required sections must survive comment-stripping."""
    monkeypatch.chdir(tmp_path)
    assert main(["new", "project", "--code", "AUR", "--name", "Aurora"]) == 0
    assert main(["new", "charter", "--project", "PRJ-001-AUR"]) == 0
    docs = sorted(str(p) for p in (tmp_path / "documents").rglob("*.md"))
    assert main(["validate", *docs]) == 0
