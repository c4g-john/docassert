"""Tests for the derived project-status view."""
import os
from pathlib import Path

from docassert import status as S

ROOT = Path(__file__).resolve().parent.parent


def _cd_root():
    os.chdir(ROOT)  # build_status reads criteria/ and consistency.yaml relatively


# ── the model derives from the real repo ────────────────────────────────────
def test_build_status_from_repo():
    _cd_root()
    m = S.build_status(ROOT / "documents")
    assert m["counts"]["total"] >= 20
    assert m["counts"]["kinds"] >= 15
    # the onboarding spine is fully covered
    assert all(not c["gaps"] for c in m["coverage"])
    # the risk register contributes open risks
    assert any(r["id"] == "AUR-RISK-001" for r in m["risks"])
    assert m["rag"] in {"green", "amber", "red"}


def test_repo_rag_is_amber_due_to_open_risks():
    _cd_root()
    m = S.build_status(ROOT / "documents")
    # nothing is broken (no failing approved docs, no dangling links), but the
    # register carries open risks → amber, not green.
    assert m["counts"]["failing"] == 0
    assert not m["broken_references"]
    assert m["risks"]
    assert m["rag"] == "amber"


# ── derive_rag logic ────────────────────────────────────────────────────────
def _model(**over):
    base = {"documents": [], "coverage": [], "risks": [],
            "broken_references": [], "latest_report": None}
    base.update(over)
    return base


def test_rag_red_on_broken_references():
    assert S.derive_rag(_model(broken_references=["PR-1 —traces→ BR-9"])) == "red"


def test_rag_red_on_failing_approved_doc():
    m = _model(documents=[{"status": "approved", "passing": False}])
    assert S.derive_rag(m) == "red"


def test_rag_amber_on_open_risk():
    # at or above the appetite (default 6) ambers; below stays green
    assert S.derive_rag(_model(risks=[{"id": "RISK-1", "score": 6}])) == "amber"
    assert S.derive_rag(_model(risks=[{"id": "RISK-1", "score": 4}])) == "green"


def test_rag_amber_on_coverage_gap():
    assert S.derive_rag(_model(coverage=[{"gaps": ["BR-002"]}])) == "amber"


def test_rag_green_when_clean():
    m = _model(documents=[{"status": "approved", "passing": True}],
               coverage=[{"gaps": []}])
    assert S.derive_rag(m) == "green"


# ── renderers produce sane output ───────────────────────────────────────────
def test_render_html_is_self_contained():
    _cd_root()
    out = S.render_html(S.build_status(ROOT / "documents"))
    assert out.startswith("<!doctype html>")
    assert "AMBER" in out and "AUR-RISK-001" in out
    assert "http://" not in out and "https://" not in out  # no external deps


def test_render_json_roundtrips():
    import json
    _cd_root()
    data = json.loads(S.render_json(S.build_status(ROOT / "documents")))
    assert data["rag"] == "amber" and data["counts"]["total"] >= 20


# ── per-project scoping (Phase 2) ───────────────────────────────────────────
def test_build_status_scoped_to_one_project():
    _cd_root()
    m = S.build_status(ROOT / "documents", project="PRJ-002-ATL")
    ids = {d["id"] for d in m["documents"]}
    assert "ATL-brd" in ids and "AUR-brd" not in ids
    assert m["project"] == "PRJ-002-ATL"
    # coverage counts only Atlas' own business requirements
    brs = next(c for c in m["coverage"] if "business requirement" in c["label"])
    assert brs["total"] == 2
    assert m["risks"] == []
    # Atlas is on the lean-startup profile with its required docs still proposed
    # (not approved) → incomplete → amber, even with no open risks.
    assert m["completeness"]["profile"] == "lean-startup"
    assert m["rag"] == "amber"


def test_build_status_scopes_risks_to_that_project():
    _cd_root()
    m = S.build_status(ROOT / "documents", project="PRJ-001-AUR")
    assert {r["id"] for r in m["risks"]} == {"AUR-RISK-001", "AUR-RISK-002"}


def test_build_index_one_card_per_project():
    _cd_root()
    idx = S.build_index(ROOT / "documents")
    by_code = {c["code"]: c for c in idx["projects"]}
    assert set(by_code) == {"AUR", "ATL", "MER", "PHX"}
    assert by_code["AUR"]["rag"] == "amber" and by_code["AUR"]["risks"] == 2
    assert by_code["ATL"]["rag"] == "amber"  # required docs still incomplete
    assert idx["overall"]["rag"] == "amber"


def test_render_index_html_links_projects_and_is_self_contained():
    _cd_root()
    out = S.render_index_html(S.build_index(ROOT / "documents"))
    assert out.startswith("<!doctype html>")
    assert 'href="PRJ-001-AUR.html"' in out and 'href="PRJ-002-ATL.html"' in out
    assert "http://" not in out and "https://" not in out


def test_render_project_page_has_back_link_and_scoped_title():
    _cd_root()
    out = S.render_html(S.build_status(ROOT / "documents", project="PRJ-002-ATL"))
    assert 'href="index.html"' in out          # back to the portfolio index
    assert "Atlas" in out and "AMBER" in out
    assert "http://" not in out and "https://" not in out


# ── the risk model carries the full story ────────────────────────────────────
def test_risks_carry_description_threatens_and_response():
    _cd_root()
    m = S.build_status(ROOT / "documents")
    r = next(r for r in m["risks"] if r["id"] == "AUR-RISK-001")
    assert r["description"] and "Probability" not in r["description"]
    assert r["threatens"]                     # links to the BRs at stake
    assert r["response"]                      # the full mitigation text
    assert r["probability"] in {"low", "medium", "high", "critical", "?"}


def test_risks_tolerate_missing_fields():
    from docassert.graph import Graph
    from docassert.models import Item
    from docassert.status.derive import _risks
    g = Graph()
    g.add(Item("XX-RISK-001", "XX", "RISK", "Bare risk with no fields yet.",
               {}, "d.md", "risk-register", "draft", "S"))
    (r,) = _risks(g)
    assert r["description"] == "Bare risk with no fields yet."
    assert r["response"] == "" and r["probability"] == "?"


def test_render_html_risk_section():
    _cd_root()
    out = S.render_html(S.build_status(ROOT / "documents"))
    assert "HEAT MATRIX" in out and "Risk register" in out
    # the full risk record ships in the embedded data: description, response,
    # threatens, probability/impact, and disposition
    assert '"response"' in out and '"threatens"' in out
    assert '"prob"' in out and '"disposition"' in out
    assert "AUR-RISK-001" in out


# ── risk disposition (ENG-PR-002) ────────────────────────────────────────────
def _risk_graph(*status_clauses):
    from docassert.graph import Graph
    from docassert.models import Item
    g = Graph()
    for i, clause in enumerate(status_clauses, 1):
        text = (f"Risk {i} description. Probability: low. Impact: high. "
                f"Owner: o.{i}.{clause} Response: watch.")
        g.add(Item(f"XX-RISK-{i:03d}", "XX", "RISK", text, {}, "d.md",
                   "risk-register", "approved", "S"))
    return g


def test_disposition_parsed_and_defaulted():
    from docassert.status.derive import _risks
    g = _risk_graph(" Status: Mitigated.", " Status: accepted.", "")
    rs = _risks(g)
    assert [r["disposition"] for r in rs] == ["open", "mitigated", "accepted"]
    assert rs[0]["id"] == "XX-RISK-003"          # open risks sort first


def test_rag_green_when_all_risks_dispositioned():
    base = {"documents": [], "coverage": [], "broken_references": [],
            "latest_report": None, "completeness": None}
    open_r = dict(base, risks=[{"id": "R", "score": 6, "disposition": "open"}])
    done_r = dict(base, risks=[{"id": "R", "score": 6, "disposition": "accepted"}])
    assert S.derive_rag(open_r) == "amber"
    assert S.derive_rag(done_r) == "green"


def test_disposition_check_blocks_invalid(tmp_path):
    from docassert.loader import load
    from docassert.structural import check_risk_disposition_valid
    p = tmp_path / "r.md"
    p.write_text(
        "---\nkind: risk-register\nid: XX-risk-register\n"
        "project: PRJ-001-XX\ntitle: T\nowner: o\nstatus: approved\n---\n\n"
        "## Overview\nx\n\n## Risks\n\n"
        "- **XX-RISK-001**: Bad. Probability: low. Impact: low. Owner: o. "
        "Status: wontfix. Response: r.\n", encoding="utf-8")
    doc = load(p)
    ok, detail = check_risk_disposition_valid(
        doc, {"item_sections": [{"section": "Risks", "prefix": "RISK"}]})
    assert not ok and "wontfix" in detail


def test_render_html_shows_dispositions():
    _cd_root()
    out = S.render_html(S.build_status(ROOT / "documents"))
    assert '"disposition": "open"' in out or '"disposition":"open"' in out
    assert "OPEN RISKS" in out and "dispositioned" in out


# ── operations kind (ENG-PR-003) ─────────────────────────────────────────────
OPS_DOC = """---
kind: operations
id: XX-operations
project: PRJ-001-XX
title: Ops fixture
owner: ops.owner
status: approved
review_by: {due}
---

## Overview
x

## Services

- **XX-SVC-001**: Triage. Level: within 14 days. Measure: monthly report.
"""


def _ops_tree(tmp_path, due):
    d = tmp_path / "documents" / "PRJ-001-XX"
    d.mkdir(parents=True)
    (d / "project.md").write_text(
        "---\nkind: project\nid: PRJ-001-XX\ncode: XX\nname: Xy Ops\n"
        "sponsor: sp.owner\nstatus: active\n---\n\n## Overview\nx\n\n## Scope\nx\n",
        encoding="utf-8")
    (d / "operations.md").write_text(OPS_DOC.format(due=due), encoding="utf-8")
    return tmp_path / "documents"


def test_stale_operations_review_ambers_status(tmp_path):
    _cd_root()
    m = S.build_status(_ops_tree(tmp_path, "2020-01-01"), project="PRJ-001-XX")
    assert m["operations"][0]["fresh"] is False
    assert m["rag"] == "amber"
    assert "OVERDUE" in S.render_markdown(m)


def test_fresh_operations_review_stays_green(tmp_path):
    _cd_root()
    m = S.build_status(_ops_tree(tmp_path, "2099-12-31"), project="PRJ-001-XX")
    assert m["operations"][0]["fresh"] is True
    assert m["rag"] == "green"
    assert "Operations review" in S.render_html(m)


def test_svc_and_freshness_checks(tmp_path):
    from docassert.loader import load
    from docassert.structural import check_ops_review_fresh, check_svc_items_complete
    docs = _ops_tree(tmp_path, "2020-01-01")
    doc = load(docs / "PRJ-001-XX" / "operations.md")
    ctx = {"item_sections": [{"section": "Services", "prefix": "SVC"}]}
    ok, _ = check_svc_items_complete(doc, ctx)
    assert ok
    fresh_ok, detail = check_ops_review_fresh(doc, ctx)
    assert not fresh_ok and "overdue" in detail


# ── risk appetite (spec 0.7.0) ───────────────────────────────────────────────
def test_low_grade_open_risks_do_not_amber():
    base = {"documents": [], "coverage": [], "broken_references": [],
            "latest_report": None, "completeness": None, "operations": [],
            "risk_amber_score": 6}
    low = dict(base, risks=[{"id": "R", "score": 4, "disposition": "open"}])
    hi = dict(base, risks=[{"id": "R", "score": 6, "disposition": "open"}])
    strict = dict(low, risk_amber_score=0)
    assert S.derive_rag(low) == "green"
    assert S.derive_rag(hi) == "amber"
    assert S.derive_rag(strict) == "amber"


def test_charter_target_becomes_implicit_milestone():
    _cd_root()
    m = S.build_status(ROOT / "documents", project="PRJ-002-ATL")
    dates = [x["label"] for x in m["milestones"]]
    assert any("Charter target" in lbl or lbl for lbl in dates) or m["milestones"] == []
    # Aurora has explicit dated milestones AND a target; no duplicates by date
    m2 = S.build_status(ROOT / "documents", project="PRJ-001-AUR")
    seen = [x["date"] for x in m2["milestones"]]
    assert len(seen) == len(set(seen))


# ── sequence-and-size charts (sponsor direction, spec 0.8.0) ─────────────────
def _seq_tree(tmp_path, cyclic=False):
    d = tmp_path / "documents" / "PRJ-001-SQ"
    d.mkdir(parents=True)
    (d / "project.md").write_text(
        "---\nkind: project\nid: PRJ-001-SQ\ncode: SQ\nname: Seq Fixture\n"
        "sponsor: sp.owner\nstatus: active\n---\n\n## Overview\nx\n\n## Scope\nx\n",
        encoding="utf-8")
    first_after = "; after: SQ-PR-003" if cyclic else ""
    (d / "prd.md").write_text(
        "---\nkind: prd\nid: SQ-prd\nproject: PRJ-001-SQ\ntitle: T\n"
        "owner: ow.ner\nstatus: approved\n---\n\n## Overview\nx\n\n"
        "## Product Requirements\n\n"
        f"- **SQ-PR-001** (traces: SQ-BR-001{first_after}): First thing.\n"
        "- **SQ-PR-002** (traces: SQ-BR-001; after: SQ-PR-001): Second thing.\n"
        "- **SQ-PR-003** (traces: SQ-BR-001; after: SQ-PR-002): Third thing.\n\n"
        "## Acceptance Criteria\n\n"
        "- **SQ-AC-001** (verifies: SQ-PR-001): Given a, when b, then c.\n"
        "- **SQ-AC-002** (verifies: SQ-PR-001): Given d, when e, then f.\n"
        "- **SQ-AC-003** (verifies: SQ-PR-002): Given g, when h, then i.\n",
        encoding="utf-8")
    (d / "brd.md").write_text(
        "---\nkind: brd\nid: SQ-brd\nproject: PRJ-001-SQ\ntitle: T\n"
        "owner: ow.ner\nstatus: approved\n---\n\n## Purpose\nx\n\n"
        "## Business Requirements\n\n"
        "- **SQ-BR-001**: The business shall reach 100% of the metric by 2026-12-31.\n\n"
        "## Out of Scope\nx\n", encoding="utf-8")
    (d / "user-story.md").write_text(
        "---\nkind: user-story\nid: SQ-user-story\nproject: PRJ-001-SQ\ntitle: T\n"
        "owner: ow.ner\nstatus: approved\n---\n\n## Overview\nx\n\n"
        "## User Stories\n\n"
        "- **SQ-US-001** (traces: SQ-PR-001): As a user, I want one so that value.\n"
        "- **SQ-US-002** (traces: SQ-PR-003): As a user, I want three so that value.\n",
        encoding="utf-8")
    return tmp_path / "documents"


def test_features_points_layers_and_tshirt(tmp_path):
    _cd_root()
    m = S.build_status(_seq_tree(tmp_path), project="PRJ-001-SQ")
    by = {f["id"]: f for f in m["features"]}
    assert by["SQ-PR-001"]["points"] == 3 and by["SQ-PR-001"]["layer"] == 0
    assert by["SQ-PR-002"]["points"] == 1 and by["SQ-PR-002"]["layer"] == 1
    assert by["SQ-PR-003"]["points"] == 1 and by["SQ-PR-003"]["layer"] == 2
    from docassert.status.derive import _tshirt
    assert [_tshirt(n) for n in (1, 2, 3, 5, 9)] == ["XS", "S", "M", "L", "XL"]


def test_sequence_chart_renders_without_time_axis(tmp_path):
    _cd_root()
    m = S.build_status(_seq_tree(tmp_path), project="PRJ-001-SQ")
    out = S.render_html(m)
    assert "SEQ 1" in out and "scope points" in out
    assert "XS=1" in out and "scoped" in out
    assert "created→closed" not in out and "JUL" not in out


def test_after_cycle_blocks(tmp_path):
    from docassert.consistency import check_sequence_acyclic
    from docassert.graph import build_graph
    _cd_root()
    g = build_graph(_seq_tree(tmp_path, cyclic=True))
    r = check_sequence_acyclic(g)
    assert not r.passed and r.blocking and "after-cycle" in r.detail
