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
    assert S.derive_rag(_model(risks=[{"id": "RISK-1", "score": 4}])) == "amber"


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


def test_render_html_risk_table():
    _cd_root()
    out = S.render_html(S.build_status(ROOT / "documents"))
    assert "<th>Risk</th>" in out and "<th>Response</th>" in out
    assert "<th>Threatens</th>" in out and "<th>Owner</th>" in out
    # severity cells are colored
    assert 'style="color:var(--bad);font-weight:600;">high</td>' in out \
        or 'style="color:var(--amber);font-weight:600;">medium</td>' in out


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
    open_r = dict(base, risks=[{"id": "R", "score": 2, "disposition": "open"}])
    done_r = dict(base, risks=[{"id": "R", "score": 2, "disposition": "accepted"}])
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


def test_render_html_shows_disposition_column():
    _cd_root()
    out = S.render_html(S.build_status(ROOT / "documents"))
    assert "<th>Status</th>" in out and "open of" in out
