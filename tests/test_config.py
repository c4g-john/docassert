"""Tests for config resolution (local override → packaged default) and `init`."""
import filecmp
from pathlib import Path

import pytest

from docassert import config

ROOT = Path(__file__).resolve().parent.parent


# ── the packaged defaults mirror the repo's root config (no drift) ──────────
def test_packaged_data_mirrors_root_config():
    for name in ("criteria", "schema", "profiles", "templates"):
        root = ROOT / name
        packaged = config.DATA_DIR / name
        assert packaged.is_dir(), f"packaged _data/{name}/ is missing"
        root_files = sorted(p.name for p in root.iterdir() if p.is_file())
        packaged_files = sorted(p.name for p in packaged.iterdir() if p.is_file())
        assert root_files == packaged_files, f"{name}/ file list differs (root vs packaged)"
        for fn in root_files:
            assert filecmp.cmp(root / fn, packaged / fn, shallow=False), \
                f"{name}/{fn} drifted between the repo root and packaged _data"
    assert filecmp.cmp(ROOT / "consistency.yaml",
                       config.DATA_DIR / "consistency.yaml", shallow=False)


# ── resolution: packaged default when there's no local config ───────────────
def test_reads_packaged_default_when_no_local(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)   # no criteria/schema/profiles here
    assert config.criteria_exists("charter")
    assert config.read_criteria("charter")["kind"] == "charter"
    assert config.read_schema("charter")["properties"]["kind"]["const"] == "charter"
    assert {"regulated-industry", "lean-startup", "agile-delivery"} <= set(config.available_profiles())


def test_local_overrides_packaged(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "criteria").mkdir()
    (tmp_path / "criteria" / "charter.criteria.yaml").write_text(
        "kind: charter\nrequired_sections: [Objective]\nchecks: []\n")
    assert config.read_criteria("charter")["required_sections"] == ["Objective"]  # local wins


def test_unknown_kind_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert not config.criteria_exists("nope")
    with pytest.raises(FileNotFoundError):
        config.read_criteria("nope")


# ── init scaffolds, and is idempotent ──────────────────────────────────────
def test_init_scaffolds_defaults(tmp_path):
    created = config.init(tmp_path)
    assert set(created) == {"criteria", "schema", "profiles", "templates", "consistency.yaml"}
    assert (tmp_path / "criteria" / "charter.criteria.yaml").is_file()
    assert (tmp_path / "schema" / "project.schema.json").is_file()
    assert (tmp_path / "consistency.yaml").is_file()
    assert config.init(tmp_path) == []  # second run creates nothing
