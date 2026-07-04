"""Regression tests for the 0.20.2 audit fixes.

Every test here reproduces a defect found in the 2026-07 full audit and
proves the fix. Names reference the finding, not the implementation, so a
future refactor keeps the behavioral contract.
"""
import json

from docassert import consistency as C
from docassert.bridge import ops
from docassert.bridge.plan import BridgePlan, plans_by_repo
from docassert.graph import Graph
from docassert.models import Item
from docassert.status import render


# ── CRITICAL: closed duplicates must never shadow the real open issue ───────
def _issue(number, state, marker, title="t"):
    return {"number": number, "state": state, "title": title,
            "body": f"<!-- docassert-bridge: {marker} -->", "labels": []}


def test_index_prefers_open_issue_over_newer_closed_duplicate():
    # GitHub lists newest first: the closed duplicate (#80) precedes the
    # real open issue (#75). The marker must key to the open one.
    issues = [_issue(80, "closed", "AUR-PR-001"), _issue(75, "open", "AUR-PR-001")]
    assert ops._index(issues)["AUR-PR-001"]["number"] == 75


def test_index_prefers_lowest_number_among_same_state():
    issues = [_issue(90, "open", "AUR-PR-001"), _issue(75, "open", "AUR-PR-001")]
    assert ops._index(issues)["AUR-PR-001"]["number"] == 75
    closed = [_issue(90, "closed", "AUR-PR-002"), _issue(75, "closed", "AUR-PR-002")]
    assert ops._index(closed)["AUR-PR-002"]["number"] == 75


def test_index_keeps_legitimately_closed_issue_when_no_duplicate():
    issues = [_issue(42, "closed", "AUR-PR-003")]
    assert ops._index(issues)["AUR-PR-003"]["number"] == 42


# ── render must not crash on malformed operations dates ─────────────────────
def _base_model(**over):
    model = {
        "rag": "amber", "project": None, "title": "T",
        "counts": {"total": 1, "kinds": 1, "approved": 1, "failing": 0},
        "coverage": [], "risks": [], "documents": [], "operations": [],
        "milestones": [], "features": [], "broken_references": [],
        "latest_report": None, "completeness": None,
    }
    model.update(over)
    return model


def test_render_html_survives_malformed_review_by():
    # '2026-13-45' is 10 characters but not a date; the renderer must not
    # raise (derive already tolerates it and marks the review stale).
    model = _base_model(operations=[
        {"id": "ops", "review_by": "2026-13-45", "fresh": False}])
    html = render.render_html(model)
    assert "2026-13-45" in html


# ── an amber page must always carry its recorded causes ─────────────────────
def test_verdict_causes_include_amber_status_report():
    model = _base_model(latest_report={"id": "sr", "period": "2026-06", "rag": "amber"})
    causes = render._verdict_causes(model)
    assert any("status report" in c for c in causes)
    assert "amber" in render._verdict(model)


def test_verdict_causes_include_profile_completeness_gaps():
    comp = {"profile": "agile-delivery", "unknown": False, "blocks": False,
            "required": [], "recommended": [], "required_total": 4,
            "required_complete": 3, "missing_required": [],
            "incomplete_required": ["runbook"], "recommended_gaps": ["adr"]}
    model = _base_model(completeness=comp)
    causes = render._verdict_causes(model)
    assert any("runbook" in c for c in causes)
    assert any("recommended" in c for c in causes)


# ── the green verdict must stay true with failing drafts ────────────────────
def test_green_verdict_does_not_claim_drafts_pass_audit():
    model = _base_model(rag="green", documents=[
        {"kind": "runbook", "id": "X-runbook", "status": "draft", "passing": False}])
    verdict = render._verdict(model)
    assert "every approved document passes audit" in verdict
    assert "draft document(s) still failing" in verdict


def test_amber_verdict_counts_risks_at_appetite_only():
    risks = [
        {"id": "T-RISK-001", "disposition": "open", "score": 9, "impact": "high",
         "probability": "high", "owner": "o", "response": "r", "threatens": [],
         "description": "d"},
        {"id": "T-RISK-002", "disposition": "open", "score": 2, "impact": "low",
         "probability": "medium", "owner": "o", "response": "r", "threatens": [],
         "description": "d"},
    ]
    model = _base_model(risks=risks, risk_amber_score=6)
    verdict = render._verdict(model)
    assert "1 risk(s) at or above the appetite" in verdict


# ── inline JSON payload must round-trip losslessly ───────────────────────────
def test_json_embed_roundtrips_closing_tags():
    original = {"t": "a </script> b", "u": "plain"}
    embedded = render._json_embed(original)
    assert "</script>" not in embedded          # parser can never see it
    assert json.loads(embedded) == original     # JSON reads \\/ as /


# ── validate refuses to guess a missing kind ─────────────────────────────────
def test_validate_fails_document_with_no_kind(tmp_path, monkeypatch, capsys):
    from docassert.cli import main
    doc = tmp_path / "documents" / "mystery.md"
    doc.parent.mkdir()
    doc.write_text("---\nid: mystery\n---\n\n## Body\ntext\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    code = main(["validate", str(doc)])
    out = capsys.readouterr().out
    assert code == 1
    assert "no `kind`" in out


# ── sub-plans are isolated; deep after-chains don't recurse out ──────────────
def test_plans_by_repo_isolates_skipped_lists():
    plan = BridgePlan(projects=[{"id": "A", "code": "A", "repo": "o/r1", "features": []},
                                {"id": "B", "code": "B", "repo": "o/r2", "features": []}],
                      skipped=[{"id": "C", "reason": "x"}])
    groups = plans_by_repo(plan)
    groups["o/r1"].skipped.append({"id": "D", "reason": "y"})
    assert len(groups["o/r2"].skipped) == 1
    assert len(plan.skipped) == 1


def test_sequence_acyclic_survives_deep_chains():
    graph = Graph()
    n = 5000
    for i in range(n):
        links = {"after": [f"T-PR-{i:05d}"]} if i else {}
        graph.add(Item(id=f"T-PR-{i + 1:05d}", project="T", type="PR",
                       text="t", links=links, doc_path="p", doc_kind="prd",
                       doc_status="draft", section="s"))
    result = C.check_sequence_acyclic(graph)
    assert result.passed


def test_sequence_acyclic_still_reports_cycles():
    graph = Graph()
    for a, b in (("T-PR-001", "T-PR-002"), ("T-PR-002", "T-PR-003"),
                 ("T-PR-003", "T-PR-001")):
        graph.add(Item(id=a, project="T", type="PR", text="t",
                       links={"after": [b]}, doc_path="p", doc_kind="prd",
                       doc_status="draft", section="s"))
    result = C.check_sequence_acyclic(graph)
    assert not result.passed
    assert "after-cycle" in result.detail


# ── pages scope filtering is per repo ────────────────────────────────────────
PROJECT_MD = """---
kind: project
id: PRJ-001-AAA
code: AAA
name: Alpha
sponsor: jane.doe
status: proposed
---

## Overview
A test project.

## Scope
Everything.
"""


def test_pages_scope_panel_excludes_other_repos_issues(tmp_path, monkeypatch):
    from docassert.cli import main
    (tmp_path / "documents" / "PRJ-001-AAA").mkdir(parents=True)
    (tmp_path / "documents" / "PRJ-001-AAA" / "project.md").write_text(
        PROJECT_MD, encoding="utf-8")
    execution = {
        "repo": None,
        "projects": [{"id": "PRJ-001-AAA", "repo": "o/r1", "features": [],
                      "stories_closed": 0, "stories_total": 0}],
        "scope": {"unverified": [{"number": 1, "title": "stray-in-r1", "repo": "o/r1"},
                                 {"number": 2, "title": "stray-in-r2", "repo": "o/r2"}],
                  "orphaned": []},
    }
    (tmp_path / "execution.json").write_text(json.dumps(execution), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["pages", "--out", "_site", "--execution", "execution.json"]) == 0
    page = (tmp_path / "_site" / "PRJ-001-AAA.html").read_text(encoding="utf-8")
    assert "stray-in-r1" in page       # this repo's stray issue is shown
    assert "stray-in-r2" not in page   # the other repo's stray issue is not


# ── board lookup falls back from user to organization owners ────────────────
def test_board_get_project_falls_back_to_organization():
    from docassert.bridge import board
    from docassert.bridge.gh import GhError

    class OrgOnlyGh:
        def graphql(self, query, **variables):
            if "user(login:" in query:
                raise GhError("Could not resolve to a User with the login of 'acme'.")
            return {"organization": {"projectV2": {
                "id": "P1", "title": "Board",
                "fields": {"nodes": [{"id": "F1", "name": "Type",
                                      "dataType": "SINGLE_SELECT",
                                      "options": [{"id": "O1", "name": "Feature"}]}]}}}}

    project = board.get_project(OrgOnlyGh(), "acme", 3)
    assert project["id"] == "P1"
    assert project["fields"]["Type"]["options"]["Feature"] == "O1"
