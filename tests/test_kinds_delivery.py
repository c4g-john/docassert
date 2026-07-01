"""Tests for the delivery & quality kinds (user-story, qa-test-plan, data-migration)."""
from docassert.loader import parse_sections
from docassert.models import Document
from docassert.structural import (
    check_has_mapping_table,
    check_measurable_exit_criteria,
    check_story_format,
)


def doc_from(body: str) -> Document:
    return Document(path="x.md", frontmatter={}, sections=parse_sections(body),
                    raw_body=body)


US_CTX = {"item_sections": [{"section": "User Stories", "prefix": "US"}]}


# ── user story format ───────────────────────────────────────────────────────
def test_story_format_passes():
    d = doc_from("## User Stories\n- **AUR-US-001** (traces: AUR-PR-014): As a new customer, "
                 "I want to self-serve, so that I start on day one.")
    assert check_story_format(d, US_CTX)[0]


def test_story_format_fails():
    d = doc_from("## User Stories\n- **AUR-US-002** (traces: AUR-PR-014): Self-serve onboarding "
                 "would be nice to have.")   # no 'As a … I want'
    ok, detail = check_story_format(d, US_CTX)
    assert not ok and "AUR-US-002" in detail


# ── measurable exit criteria ────────────────────────────────────────────────
def test_exit_criteria_measurable_passes():
    d = doc_from("## Exit Criteria\n- At least 95% of test cases pass.\n"
                 "- No more than 3 open SEV-2 defects.")
    assert check_measurable_exit_criteria(d, {})[0]


def test_exit_criteria_unmeasurable_fails():
    d = doc_from("## Exit Criteria\n- Testing feels complete.\n- The team is happy.")
    assert not check_measurable_exit_criteria(d, {})[0]


# ── field mapping table ─────────────────────────────────────────────────────
def test_mapping_table_present_passes():
    d = doc_from("## Field Mapping\n| Source | Target | Transform |\n|---|---|---|\n"
                 "| a | b.c | trim |")
    ok, detail = check_has_mapping_table(d, {})
    assert ok and "1 row" in detail


def test_mapping_table_absent_fails():
    d = doc_from("## Field Mapping\nWe will map the fields somehow.")
    assert not check_has_mapping_table(d, {})[0]
