"""Tests for the shields.io status-badge endpoint output."""
import json
from pathlib import Path

from docassert import status as S
from docassert.cli import main

ROOT = Path(__file__).resolve().parent.parent


def test_badge_payload_shape_and_colors():
    for rag, color in (("green", "brightgreen"), ("amber", "orange"), ("red", "red")):
        data = json.loads(S.render_badge_json(rag))
        assert data == {"schemaVersion": 1, "label": "pmo docs",
                        "message": rag, "color": color}
    assert json.loads(S.render_badge_json("green", label="aur"))["label"] == "aur"


def test_pages_emits_badges(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "site"
    assert main(["pages", "--out", str(out)]) == 0
    overall = json.loads((out / "badge.json").read_text())
    assert overall["schemaVersion"] == 1 and overall["message"] in {"green", "amber", "red"}
    aur = json.loads((out / "badges" / "PRJ-001-AUR.json").read_text())
    assert aur["label"] == "aur" and aur["message"] in {"green", "amber", "red"}


def test_pages_execution_panels(tmp_path, monkeypatch):
    import json
    monkeypatch.chdir(ROOT)
    exec_file = tmp_path / "execution.json"
    exec_file.write_text(json.dumps({
        "repo": "o/r",
        "projects": [{"id": "PRJ-001-AUR",
                      "features": [{"id": "AUR-PR-014", "issue": 5,
                                    "stories_total": 2, "stories_closed": 1,
                                    "closed": False}],
                      "stories_closed": 1, "stories_total": 2}],
        "scope": {"unverified": [], "orphaned": []},
    }))
    out = tmp_path / "site"
    assert main(["pages", "--out", str(out), "--execution", str(exec_file)]) == 0
    html = (out / "PRJ-001-AUR.html").read_text()
    assert "1/2 stories closed" in html
    assert "AUR-PR-014" in html and "every open issue matches" in html
    other = (out / "PRJ-002-ATL.html").read_text()
    assert "Delivery ·" not in other   # no execution data, no panel
