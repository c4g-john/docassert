"""Tests for item parsing and the cross-document graph."""
from pathlib import Path

from docassert.graph import build_graph
from docassert.loader import ITEM_RE, parse_link_clause

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "documents"


def test_parse_link_clause():
    assert parse_link_clause("traces: AUR-BR-001, AUR-BR-002; verifies: AUR-FR-3") == {
        "traces": ["AUR-BR-001", "AUR-BR-002"], "verifies": ["AUR-FR-3"]}


def test_parse_link_clause_empty():
    assert parse_link_clause("") == {}


def test_item_regex_splits_project_and_type():
    m = ITEM_RE.match("**AUR-PR-014** (traces: AUR-BR-001): the flow shall be self-serve.")
    assert m and m.group("id") == "AUR-PR-014"
    assert m.group("project") == "AUR" and m.group("type") == "PR"
    assert m.group("text").startswith("the flow")


def test_item_regex_no_links():
    m = ITEM_RE.match("**AUR-BR-001**: the business shall reduce onboarding time.")
    assert m and m.group("id") == "AUR-BR-001" and m.group("links") is None


def test_build_graph_extracts_items():
    g = build_graph(DOCS)
    for iid in ("AUR-BR-001", "AUR-BR-002", "AUR-PR-014", "AUR-PR-015",
                "AUR-FR-101", "AUR-NFR-05", "AUR-AC-001", "AUR-AC-002",
                "AUR-TC-001", "AUR-TC-002"):
        assert g.exists(iid), f"missing {iid}"
    # by_type indexes across all projects
    assert {i.id for i in g.by_type["PR"]} == {
        "AUR-PR-014", "AUR-PR-015", "ATL-PR-001", "ATL-PR-002"}


def test_build_graph_links_and_children():
    g = build_graph(DOCS)
    assert "AUR-BR-001" in g.canonical("AUR-PR-014").targets("traces")
    assert [c.id for c in g.children("AUR-BR-001", "traces", "PR")] == ["AUR-PR-014"]
    assert [c.id for c in g.children("AUR-AC-001", "tests", "TC")] == ["AUR-TC-001"]


def test_multi_project_item_ids_coexist():
    """The same type+number in two projects is globally unique via the code prefix."""
    g = build_graph(DOCS)
    assert g.exists("AUR-BR-001") and g.exists("ATL-BR-001")
    assert {"AUR", "ATL"} <= set(g.by_project)
    assert g.canonical("AUR-BR-001").project == "AUR"
    assert g.canonical("ATL-BR-001").project == "ATL"
    # a cross-project id clash cannot happen: the ids differ by prefix
    assert g.canonical("AUR-BR-001") is not g.canonical("ATL-BR-001")
