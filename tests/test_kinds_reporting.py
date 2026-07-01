"""Tests for the report & close kinds (status-report, benefits-realization)."""
from docassert.loader import parse_sections
from docassert.models import Document
from docassert.structural import check_measurable_items, check_references_risk


def doc_from(body: str) -> Document:
    return Document("x.md", {}, parse_sections(body), body)


# ── measurable items (generic) ──────────────────────────────────────────────
def test_measurable_items_passes():
    d = doc_from("## Benefits\n- Reduce tickets by at least 80%.\n"
                 "- Cut onboarding below 48 hours.")
    assert check_measurable_items(d, {"measurable_sections": ["Benefits"]})[0]


def test_measurable_items_fails():
    d = doc_from("## Benefits\n- Make customers much happier.\n- Improve things.")
    assert not check_measurable_items(d, {"measurable_sections": ["Benefits"]})[0]


def test_measurable_items_no_specs_passes():
    d = doc_from("## Whatever\nprose")
    assert check_measurable_items(d, {})[0]


# ── references a risk ───────────────────────────────────────────────────────
def test_references_risk_passes():
    d = doc_from("## Risks & Issues\n- AUR-RISK-001 is now the top risk this period.")
    ok, detail = check_references_risk(d, {})
    assert ok and "AUR-RISK-001" in detail


def test_references_risk_fails_without_ids():
    d = doc_from("## Risks & Issues\n- Some things are risky but unnamed.")
    assert not check_references_risk(d, {})[0]
