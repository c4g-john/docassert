"""Tests for the risk & governance kinds (risk-register, adr, raci-stakeholder)."""
from docassert.loader import parse_sections
from docassert.models import Document
from docassert.structural import (
    check_adr_items_have_status,
    check_raci_one_accountable,
    check_risk_items_complete,
)


def doc_from(body: str) -> Document:
    return Document(path="x.md", frontmatter={}, sections=parse_sections(body),
                    raw_body=body)


RISK_CTX = {"item_sections": [{"section": "Risks", "prefix": "RISK"}]}
ADR_CTX = {"item_sections": [{"section": "Decisions", "prefix": "ADR"}]}


# ── risk items ──────────────────────────────────────────────────────────────
def test_risk_complete_passes():
    d = doc_from("## Risks\n- **AUR-RISK-001** (threatens: AUR-BR-001): migration may slip. "
                 "Probability: High. Impact: High. Owner: alex.kim. Response: dual-run.")
    assert check_risk_items_complete(d, RISK_CTX)[0]


def test_risk_missing_fields_fails():
    d = doc_from("## Risks\n- **AUR-RISK-002** (threatens: AUR-BR-001): vendor late. "
                 "Probability: High. Owner: alex.kim.")   # no Impact, no Response
    ok, detail = check_risk_items_complete(d, RISK_CTX)
    assert not ok and "Impact" in detail and "Response" in detail


# ── adr status ──────────────────────────────────────────────────────────────
def test_adr_valid_status_passes():
    d = doc_from("## Decisions\n- **AUR-ADR-001** (affects: AUR-FR-1): use SSR. Status: accepted. "
                 "Context: c. Decision: d. Consequences: e.")
    assert check_adr_items_have_status(d, ADR_CTX)[0]


def test_adr_invalid_status_fails():
    d = doc_from("## Decisions\n- **AUR-ADR-002**: pick a db. Status: maybe.")
    assert not check_adr_items_have_status(d, ADR_CTX)[0]


# ── raci one accountable ────────────────────────────────────────────────────
def test_raci_one_accountable_passes():
    d = doc_from("## RACI Matrix\n| Activity | Sponsor | Lead |\n|---|---|---|\n"
                 "| Approve | A | C |\n| Build | I | A |")
    assert check_raci_one_accountable(d, {})[0]


def test_raci_zero_accountable_fails():
    d = doc_from("## RACI Matrix\n| Activity | Sponsor | Lead |\n|---|---|---|\n"
                 "| Approve | C | C |")   # no A
    ok, detail = check_raci_one_accountable(d, {})
    assert not ok and "Approve" in detail


def test_raci_two_accountable_fails():
    d = doc_from("## RACI Matrix\n| Activity | Sponsor | Lead |\n|---|---|---|\n"
                 "| Approve | A | A |")   # two A
    assert not check_raci_one_accountable(d, {})[0]
