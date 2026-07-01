"""Tests for the project registry and the project-anchor structural check."""
from pathlib import Path

import yaml

from docassert import projects as P
from docassert.models import Document
from docassert.structural import check_project_id_format

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "documents"


# ── the registry derives from the project.md anchors ────────────────────────
def test_load_projects_finds_all_four():
    plist = P.load_projects(DOCS)
    assert [p["id"] for p in plist] == [
        "PRJ-001-AUR", "PRJ-002-ATL", "PRJ-003-MER", "PRJ-004-PHX"]
    assert {p["code"] for p in plist} == {"AUR", "ATL", "MER", "PHX"}


def test_repo_registry_has_no_issues():
    assert P.registry_issues(P.load_projects(DOCS)) == []


def test_registry_detects_duplicate_code():
    dupes = [{"id": "PRJ-001-AUR", "code": "AUR"},
             {"id": "PRJ-009-AUR", "code": "AUR"}]
    issues = P.registry_issues(dupes)
    assert any("duplicate project code: AUR" in i for i in issues)


def test_render_yaml_roundtrips():
    data = yaml.safe_load(P.render_yaml(P.load_projects(DOCS)))
    assert len(data["projects"]) == 4
    first = data["projects"][0]
    assert first["id"] == "PRJ-001-AUR" and first["code"] == "AUR"
    assert "path" not in first  # the registry omits filesystem paths


# ── the project-id-format structural check ──────────────────────────────────
def _proj(idv, code):
    return Document("p.md", {"kind": "project", "id": idv, "code": code}, {}, "")


def test_project_id_format_ok():
    assert check_project_id_format(_proj("PRJ-001-AUR", "AUR"), {})[0]


def test_project_id_format_rejects_bad_pattern():
    ok, detail = check_project_id_format(_proj("AURORA", "AUR"), {})
    assert not ok and "PRJ-NNN-CODE" in detail


def test_project_id_format_rejects_code_mismatch():
    ok, detail = check_project_id_format(_proj("PRJ-001-AUR", "ATL"), {})
    assert not ok and "tail" in detail
