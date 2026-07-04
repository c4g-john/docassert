"""Configuration resolution: local repo override → packaged default.

docassert ships default criteria, schemas, profiles, templates, and
consistency.yaml as package data under ``docassert/_data/``. At runtime each is
resolved from the current working directory first (so a repo can define its own
standard), falling back to the packaged default — which is what makes
``docassert`` usable in a repo that hasn't set up its own config.

``docassert init`` copies the packaged defaults into a repo so they can be edited.
"""
from __future__ import annotations

import json
import shutil
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

import yaml

# A concrete filesystem path to the bundled defaults (docassert is installed
# unzipped, so this resolves to a real directory for both wheel and editable installs).
DATA_DIR = Path(str(files("docassert"))) / "_data"


def _resolve(local: Path, packaged_rel: str) -> Path | None:
    """The local file if it exists, else the packaged default, else None."""
    if local.is_file():
        return local
    packaged = DATA_DIR / packaged_rel
    return packaged if packaged.is_file() else None


# Criteria and schemas are read once per check per document, which multiplies
# fast on a portfolio (projects × documents × checks). Cache on (path, mtime)
# so an edit mid-process still invalidates. Cached objects are shared: callers
# treat them as read-only.
@lru_cache(maxsize=256)
def _read_yaml_cached(path_str: str, mtime_ns: int) -> dict:
    return yaml.safe_load(Path(path_str).read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=256)
def _read_json_cached(path_str: str, mtime_ns: int) -> dict:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict:
    return _read_yaml_cached(str(path), path.stat().st_mtime_ns)


# ── criteria ────────────────────────────────────────────────────────────────
def criteria_path(kind: str) -> Path | None:
    return _resolve(Path("criteria") / f"{kind}.criteria.yaml",
                    f"criteria/{kind}.criteria.yaml")


def criteria_exists(kind: str) -> bool:
    return criteria_path(kind) is not None


def read_criteria(kind: str) -> dict:
    path = criteria_path(kind)
    if path is None:
        raise FileNotFoundError(
            f"no criteria for kind '{kind}' (looked in ./criteria and packaged defaults)")
    return _read_yaml(path)


# ── schema ──────────────────────────────────────────────────────────────────
def read_schema(kind: str) -> dict:
    path = _resolve(Path("schema") / f"{kind}.schema.json", f"schema/{kind}.schema.json")
    if path is None:
        raise FileNotFoundError(f"no schema for kind '{kind}'")
    return _read_json_cached(str(path), path.stat().st_mtime_ns)


# ── consistency config ──────────────────────────────────────────────────────
def read_consistency_config() -> dict:
    path = _resolve(Path("consistency.yaml"), "consistency.yaml")
    return _read_yaml(path) if path is not None else {}


# ── templates ───────────────────────────────────────────────────────────────
def template_path(kind: str) -> Path | None:
    return _resolve(Path("templates") / f"{kind}.template.md",
                    f"templates/{kind}.template.md")


def available_kinds() -> list[str]:
    """Every kind with criteria, local and packaged."""
    names: set[str] = set()
    local = Path("criteria")
    if local.is_dir():
        names |= {p.name.removesuffix(".criteria.yaml") for p in local.glob("*.criteria.yaml")}
    packaged = DATA_DIR / "criteria"
    if packaged.is_dir():
        names |= {p.name.removesuffix(".criteria.yaml") for p in packaged.glob("*.criteria.yaml")}
    return sorted(names)


# ── profiles ────────────────────────────────────────────────────────────────
def profile_path(name: str) -> Path | None:
    return _resolve(Path("profiles") / f"{name}.yaml", f"profiles/{name}.yaml")


def available_profiles() -> list[str]:
    names: set[str] = set()
    local = Path("profiles")
    if local.is_dir():
        names |= {p.stem for p in local.glob("*.yaml")}
    packaged = DATA_DIR / "profiles"
    if packaged.is_dir():
        names |= {p.stem for p in packaged.glob("*.yaml")}
    return sorted(names)


# ── scaffolding (docassert init) ────────────────────────────────────────────
# (packaged source, destination in the repo). The doc-to-pmo Claude skill lands
# under .claude/skills/ so Claude Code discovers it in the user's repo.
_INIT_TREE = [
    ("criteria", "criteria"),
    ("schema", "schema"),
    ("profiles", "profiles"),
    ("templates", "templates"),
    ("consistency.yaml", "consistency.yaml"),
    ("skills", ".claude/skills"),
]


def init(dest: str | Path = ".") -> list[str]:
    """Copy the packaged defaults into `dest`, skipping anything already present.
    Returns the destination names that were created."""
    dest = Path(dest)
    created: list[str] = []
    for src_name, dest_name in _INIT_TREE:
        target = dest / dest_name
        if target.exists():
            continue
        src = DATA_DIR / src_name
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(dest_name)
    return created
