"""Tests for check severities: integrity always blocks; completeness relaxes
to advisory while a document is a draft ("WIP is never punished")."""
from pathlib import Path

from docassert.cli import main
from docassert.loader import parse_sections
from docassert.models import Document
from docassert.structural import (
    _effective_blocking,
    check_dates_consistent,
    check_frontmatter_complete,
    check_frontmatter_schema,
)

ROOT = Path(__file__).resolve().parent.parent

DRAFT_CHARTER = """---
kind: charter
project: PRJ-001-TST
id: TST-charter
title: T — Draft Charter
sponsor: jane.doe
dates:
  created: 2026-01-01
status: {status}
---

## Objective
Cut cycle time from 10 days to under 2 days.

## Success Criteria
- Median cycle time drops below 48 hours.

## Scope
In scope: the thing.

## Milestones
- TODO: none yet.

## Risks
- Might slip. Owner: jane.doe. Mitigation: buffer.

## Approval
Pending.
"""


def _write(tmp_path, status):
    d = tmp_path / "documents" / "PRJ-001-TST"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "charter.md"
    f.write_text(DRAFT_CHARTER.format(status=status), encoding="utf-8")
    return f


# ── the Refuge scenario: an incomplete DRAFT merges (advisory only) ──────────
def test_draft_missing_budget_is_advisory(tmp_path, monkeypatch, capsys):
    f = _write(tmp_path, "draft")
    monkeypatch.chdir(tmp_path)
    assert main(["validate", str(f)]) == 0          # no blocking failures
    out = capsys.readouterr().out
    assert "Missing required frontmatter" in out    # ...but the gap is reported
    assert "budget" in out


def test_proposed_missing_budget_blocks(tmp_path, monkeypatch):
    f = _write(tmp_path, "proposed")
    monkeypatch.chdir(tmp_path)
    assert main(["validate", str(f)]) >= 1          # completeness now gates


def test_type_error_blocks_even_on_draft(tmp_path, monkeypatch):
    f = _write(tmp_path, "draft")
    f.write_text(f.read_text().replace("sponsor: jane.doe", "sponsor: j"),
                 encoding="utf-8")                  # minLength violation = malformed
    monkeypatch.chdir(tmp_path)
    assert main(["validate", str(f)]) >= 1


def test_malformed_item_blocks_even_on_draft(tmp_path, monkeypatch):
    d = tmp_path / "documents" / "PRJ-001-TST"
    d.mkdir(parents=True)
    (d / "brd.md").write_text("""---
kind: brd
project: PRJ-001-TST
id: TST-brd
title: T
owner: jane.doe
status: draft
---

## Purpose
p.

## Business Requirements
- **broken bullet** without a valid item id

## Out of Scope
n/a
""", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["validate", str(d / "brd.md")]) >= 1   # integrity: always blocks


# ── the split checks ─────────────────────────────────────────────────────────
def _doc(fm):
    return Document("x.md", fm, parse_sections(""), "")


def test_schema_vs_complete_split():
    import json
    schema = json.loads((ROOT / "schema" / "charter.schema.json").read_text())
    ctx = {"schema": schema}
    doc = _doc({"kind": "charter", "id": "TST-charter", "project": "PRJ-001-TST",
                "title": "Test Charter", "sponsor": "jane.doe", "status": "draft"})  # no budget/dates
    ok_schema, _ = check_frontmatter_schema(doc, ctx)
    ok_complete, detail = check_frontmatter_complete(doc, ctx)
    assert ok_schema                     # nothing malformed
    assert not ok_complete and "budget" in detail


def test_dates_absent_pass_invalid_fail():
    assert check_dates_consistent(_doc({"dates": {}}), {})[0]
    assert check_dates_consistent(_doc({}), {})[0]
    ok, detail = check_dates_consistent(_doc({"dates": {"created": "soonish"}}), {})
    assert not ok and "soonish" in detail


# ── blocking interpretation ──────────────────────────────────────────────────
def test_effective_blocking_modes():
    draft, proposed = _doc({"status": "draft"}), _doc({"status": "proposed"})
    assert _effective_blocking({"blocking": True}, draft)
    assert _effective_blocking({"blocking": "always"}, draft)
    assert not _effective_blocking({"blocking": False}, proposed)
    assert not _effective_blocking({"blocking": "never"}, proposed)
    assert not _effective_blocking({"blocking": "once-proposed"}, draft)
    assert _effective_blocking({"blocking": "once-proposed"}, proposed)
    assert not _effective_blocking({"blocking": "once-proposed"}, _doc({}))  # no status = draft
