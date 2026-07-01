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
