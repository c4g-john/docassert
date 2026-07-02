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
