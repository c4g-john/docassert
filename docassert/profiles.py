"""Profiles — the expected document set for a project.

A profile (profiles/<name>.yaml) lists the document kinds a project is expected
to carry, at two levels:
  - required    : must be present and complete; a missing one blocks CI once the
                  project reaches the profile's `enforce_when` lifecycle stage.
  - recommended : surfaced as a gap on the project page, but never blocking.

A project opts in with `profile: <name>` in its project.md. No profile means no
completeness expectations (fully backward-compatible).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import config as config_mod

APPROVED = {"approved", "baselined"}


def available(profiles_dir: str | Path | None = None) -> list[str]:
    """Profile names. Default resolves local ./profiles + packaged defaults; pass
    an explicit dir to look only there."""
    if profiles_dir is not None:
        d = Path(profiles_dir)
        return sorted(p.stem for p in d.glob("*.yaml")) if d.is_dir() else []
    return config_mod.available_profiles()


def load_profile(name: str, profiles_dir: str | Path | None = None) -> dict | None:
    """Load one profile, or None if there is no such file. Default resolves
    ./profiles then the packaged defaults; pass an explicit dir to override."""
    if profiles_dir is not None:
        candidate = Path(profiles_dir) / f"{name}.yaml"
        path = candidate if candidate.is_file() else None
    else:
        path = config_mod.profile_path(name)
    if path is None:
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    expects = data.get("expects", {}) or {}
    return {
        "name": data.get("name", name),
        "enforce_when": data.get("enforce_when", "active"),
        "required": list(expects.get("required", []) or []),
        "recommended": list(expects.get("recommended", []) or []),
    }


def _kind_state(kind: str, by_kind: dict[str, list[dict]]) -> str:
    """complete / incomplete / missing for one expected kind.

    complete   = at least one document of the kind is approved/baselined AND
                 passing its audit.
    incomplete = present, but none is complete yet (draft/proposed or failing).
    missing    = no document of the kind at all.
    """
    docs = by_kind.get(kind, [])
    if not docs:
        return "missing"
    if any(str(d.get("status", "")).lower() in APPROVED and d.get("passing", True)
           for d in docs):
        return "complete"
    return "incomplete"


def completeness(profile: dict, documents: list[dict], project_status: str) -> dict:
    """Assess a project's documents against its profile.

    `documents` is a list of {kind, status, passing} dicts (the project's docs).
    """
    by_kind: dict[str, list[dict]] = {}
    for d in documents:
        by_kind.setdefault(d.get("kind"), []).append(d)

    required = [{"kind": k, "state": _kind_state(k, by_kind)} for k in profile["required"]]
    recommended = [{"kind": k, "state": _kind_state(k, by_kind)} for k in profile["recommended"]]

    missing_required = [r["kind"] for r in required if r["state"] == "missing"]
    incomplete_required = [r["kind"] for r in required if r["state"] == "incomplete"]
    recommended_gaps = [r["kind"] for r in recommended if r["state"] != "complete"]

    enforced = str(project_status).lower() == str(profile["enforce_when"]).lower()
    return {
        "profile": profile["name"],
        "enforce_when": profile["enforce_when"],
        "enforced": enforced,
        "unknown": False,
        "required": required,
        "recommended": recommended,
        "required_total": len(required),
        "required_complete": sum(1 for r in required if r["state"] == "complete"),
        "missing_required": missing_required,
        "incomplete_required": incomplete_required,
        "recommended_gaps": recommended_gaps,
        # A missing required document blocks only once the project is enforced.
        "blocks": enforced and bool(missing_required),
    }


def unknown(profile_name: str) -> dict:
    """Placeholder completeness for a project that names a non-existent profile."""
    return {
        "profile": profile_name, "enforce_when": None, "enforced": False,
        "unknown": True, "required": [], "recommended": [],
        "required_total": 0, "required_complete": 0,
        "missing_required": [], "incomplete_required": [], "recommended_gaps": [],
        "blocks": False,
    }
