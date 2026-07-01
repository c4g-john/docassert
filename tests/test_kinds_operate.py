"""Tests for the release & operate kinds' numbered-steps check."""
from docassert.loader import parse_sections
from docassert.models import Document
from docassert.structural import check_numbered_steps


def doc_from(body: str) -> Document:
    return Document("x.md", {}, parse_sections(body), body)


def test_numbered_steps_passes():
    d = doc_from("## Cutover Steps\n1. Freeze writes.\n2. Migrate.\n3. Verify.")
    assert check_numbered_steps(d, {"steps_sections": ["Cutover Steps"]})[0]


def test_numbered_steps_too_few_fails():
    d = doc_from("## Cutover Steps\n1. Just do it.")
    ok, detail = check_numbered_steps(d, {"steps_sections": ["Cutover Steps"]})
    assert not ok and "Cutover Steps" in detail


def test_numbered_steps_no_specs_passes():
    d = doc_from("## Whatever\nsome prose")
    assert check_numbered_steps(d, {})[0]
