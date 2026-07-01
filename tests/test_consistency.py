"""Tests for the cross-document consistency engine."""
from pathlib import Path

from docassert import rtm
from docassert.consistency import (
    check_coverage,
    check_referential_integrity,
    check_required_links,
    check_unique_item_ids,
    load_config,
    run_consistency,
)
from docassert.graph import Graph, build_graph
from docassert.models import Item

ROOT = Path(__file__).resolve().parent.parent
CONFIG = load_config(ROOT / "consistency.yaml")


def mk(iid, type_, links=None, status="approved", project="AUR"):
    return Item(iid, project, type_, f"{iid} text", links or {}, "d.md", "k", status, "S")


def graph_of(*items):
    g = Graph()
    for it in items:
        g.add(it)
    return g


# ── referential integrity (always blocks) ──────────────────────────────────
def test_referential_integrity_ok():
    g = graph_of(mk("BR-001", "BR"), mk("PR-014", "PR", {"traces": ["BR-001"]}))
    assert check_referential_integrity(g).passed


def test_referential_integrity_broken_ref_caught():
    g = graph_of(mk("PR-014", "PR", {"traces": ["BR-999"]}))
    r = check_referential_integrity(g)
    assert not r.passed and "BR-999" in r.detail and r.blocking


# ── coverage (blocks only when approved) ────────────────────────────────────
def test_coverage_enforced_when_approved():
    g = graph_of(mk("BR-001", "BR", status="approved"))  # no covering PR
    assert not check_coverage(g, CONFIG).passed


def test_coverage_skipped_when_draft():
    g = graph_of(mk("BR-001", "BR", status="draft"))     # no covering PR, but draft
    assert check_coverage(g, CONFIG).passed


def test_coverage_satisfied():
    g = graph_of(mk("BR-001", "BR", status="approved"),
                 mk("PR-014", "PR", {"traces": ["BR-001"]}, status="approved"),
                 mk("AC-001", "AC", {"verifies": ["PR-014"]}, status="approved"),
                 mk("TC-001", "TC", {"tests": ["AC-001"]}, status="approved"))
    assert check_coverage(g, CONFIG).passed


# ── required links / orphans (blocks only when approved) ────────────────────
def test_orphan_blocks_when_approved():
    g = graph_of(mk("PR-014", "PR", status="approved"))  # no traces link
    assert not check_required_links(g, CONFIG).passed


def test_orphan_ok_when_draft():
    g = graph_of(mk("PR-014", "PR", status="draft"))
    assert check_required_links(g, CONFIG).passed


# ── uniqueness (always blocks) ──────────────────────────────────────────────
def test_duplicate_item_ids_caught():
    g = graph_of(mk("BR-001", "BR"), mk("BR-001", "BR"))
    r = check_unique_item_ids(g)
    assert not r.passed and "BR-001" in r.detail


# ── the real repo spine is fully consistent ─────────────────────────────────
def test_repo_consistency_has_no_blocking_failures():
    results = run_consistency(ROOT / "documents", ROOT / "consistency.yaml",
                              with_semantic=False)
    assert not any(r.is_blocking_failure for r in results)


def test_rtm_renders_full_chain():
    rows = rtm.build_rows(build_graph(ROOT / "documents"))
    by_br = {r["BR"]: r for r in rows}
    assert by_br["AUR-BR-001"]["PR"] == {"AUR-PR-014"}
    assert by_br["AUR-BR-001"]["TC"] == {"AUR-TC-001"}
    assert all(r["PR"] for r in rows)  # no uncovered business requirement


def test_rtm_scopes_to_one_project():
    g = build_graph(ROOT / "documents")
    aur = {r["BR"] for r in rtm.build_rows(g, project="AUR")}
    atl = {r["BR"] for r in rtm.build_rows(g, project="ATL")}
    assert aur == {"AUR-BR-001", "AUR-BR-002"}
    assert atl == {"ATL-BR-001", "ATL-BR-002"}
