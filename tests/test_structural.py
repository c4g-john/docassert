"""Unit tests for the deterministic checker.

The validator that unit-tests business documents is itself unit-tested.
"""
import json
from pathlib import Path

import pytest

from docassert.loader import load, load_criteria, parse_sections
from docassert.structural import CHECKS, _field_value, _is_measurable, run_structural

ROOT = Path(__file__).resolve().parent.parent
AURORA = ROOT / "documents" / "PRJ-001-AUR" / "charter.md"
WEAK = ROOT / "tests" / "fixtures" / "weak-example.md"


def _ctx(extra_docs=()):
    schema = json.loads((ROOT / "schema" / "charter.schema.json").read_text())
    criteria = load_criteria(ROOT / "criteria" / "charter.criteria.yaml")
    id_index = {}
    for p in [AURORA, WEAK, *extra_docs]:
        doc = load(p)
        id_index.setdefault(doc.id, []).append(str(p))
    return {
        "schema": schema,
        "required_sections": criteria["required_sections"],
        "id_index": id_index,
    }


def _run_all(doc_path):
    doc = load(doc_path)
    criteria = load_criteria(ROOT / "criteria" / "charter.criteria.yaml")
    ctx = _ctx()
    results = {}
    for spec in criteria["checks"]:
        if spec["type"] == "structural":
            results[spec["id"]] = run_structural(doc, spec, ctx)
    return results


# ── the good charter passes every structural check ─────────────────────────
def test_aurora_passes_all_structural():
    results = _run_all(AURORA)
    failures = {cid: r.detail for cid, r in results.items() if not r.passed}
    assert failures == {}, f"aurora should pass but failed: {failures}"


# ── the weak charter fails exactly the checks we expect ────────────────────
def test_weak_fails_measurable_criteria():
    results = _run_all(WEAK)
    assert not results["measurable-success-criteria"].passed


def test_weak_fails_risks_owner_mitigation():
    results = _run_all(WEAK)
    assert not results["risks-have-owner-and-mitigation"].passed


def test_weak_fails_dates_consistent():
    results = _run_all(WEAK)  # target 2026-02-01 is before created 2026-03-01
    assert not results["dates-consistent"].passed


def test_weak_has_blocking_failures():
    results = _run_all(WEAK)
    assert any(r.is_blocking_failure for r in results.values())


# ── measurability heuristic ────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "Median onboarding time drops below 48 hours",
    "CSAT rises above 4.5 / 5",
    "Manual tickets fall by at least 80%",
    "Reduce spend under $1.2M",
    "Ship by 2026-09-30",
])
def test_measurable_true(text):
    assert _is_measurable(text)


@pytest.mark.parametrize("text", [
    "Improve onboarding",
    "Make customers happier",
    "Reduce friction in the process",
    "Deliver a best-in-class experience",
])
def test_measurable_false(text):
    assert not _is_measurable(text)


# ── owner/mitigation field extraction ──────────────────────────────────────
def test_field_value_present():
    item = "Data migration may slip. Owner: alex.kim. Mitigation: dual-run."
    assert _field_value(item, "owner") == "alex.kim"
    assert _field_value(item, "mitigation") == "dual-run"


def test_field_value_absent():
    assert _field_value("Timeline might slip.", "owner") is None


# ── section parsing ────────────────────────────────────────────────────────
def test_parse_sections():
    body = "## Objective\nDo the thing.\n\n## Risks\n- A risk. Owner: x. Mitigation: y."
    sections = parse_sections(body)
    assert set(sections) == {"Objective", "Risks"}
    assert sections["Risks"].list_items == ["A risk. Owner: x. Mitigation: y."]


# ── every configured structural check has an implementation ────────────────
def test_all_structural_checks_implemented():
    criteria = load_criteria(ROOT / "criteria" / "charter.criteria.yaml")
    for spec in criteria["checks"]:
        if spec["type"] == "structural":
            assert spec["id"] in CHECKS, f"no implementation for {spec['id']}"
