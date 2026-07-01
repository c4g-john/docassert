"""Deterministic structural checks. These are reliable and BLOCKING."""
from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable

from jsonschema import Draft7Validator, FormatChecker

from .loader import iter_item_lines
from .models import CheckResult, Document

# ── measurability heuristic ────────────────────────────────────────────────
# A success criterion is "measurable" if it contains a number AND either a
# comparator or a unit/symbol/date — enough to make pass/fail unambiguous.
_NUMBER = re.compile(r"\d")
_COMPARATOR = re.compile(
    r"[<>]=?|\b(?:below|under|above|over|at least|at most|no more than|"
    r"no less than|fewer than|more than|greater than|less than|within|by|"
    r"reach|reduce|increase|decrease|drop|rise|cut|from|to)\b",
    re.IGNORECASE,
)
_UNIT_OR_SYMBOL = re.compile(
    r"%|[$€£]|/\s*\d|\d{4}-\d{2}-\d{2}|"
    r"\b(?:hours?|hrs?|days?|weeks?|months?|minutes?|mins?|seconds?|secs?|"
    r"USD|EUR|GBP|k|m|bn|pts?|points?|x)\b",
    re.IGNORECASE,
)


def _is_measurable(text: str) -> bool:
    if not _NUMBER.search(text):
        return False
    return bool(_COMPARATOR.search(text) or _UNIT_OR_SYMBOL.search(text))


def _field_value(item: str, field: str) -> str | None:
    """Return the text after `field:` (up to a sentence/clause break), or None.

    Stops at a semicolon or a period that ends a clause (period + space, or
    period at end) so dotted handles like ``alex.kim`` are not truncated.
    """
    m = re.search(rf"{field}\s*:\s*(.+?)(?:;|\.\s|\.$|$)", item, re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).strip()
    return val if len(val) >= 2 else None


def _jsonify(value):
    """Convert YAML date/datetime objects to ISO strings so a JSON Schema with
    `type: string, format: date` validates correctly."""
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def _as_date(value) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


# ── individual checks ──────────────────────────────────────────────────────
def check_frontmatter_schema(doc: Document, ctx: dict) -> tuple[bool, str]:
    schema = ctx["schema"]
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(_jsonify(doc.frontmatter)), key=str)
    if not errors:
        return True, "Frontmatter is valid against the schema."
    msgs = "; ".join(f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
                     for e in errors)
    return False, f"Frontmatter schema errors: {msgs}"


def check_required_sections(doc: Document, ctx: dict) -> tuple[bool, str]:
    required = ctx["required_sections"]
    missing = [s for s in required if s not in doc.sections]
    empty = [s for s in required if s in doc.sections and doc.sections[s].is_empty]
    problems = []
    if missing:
        problems.append(f"missing: {', '.join(missing)}")
    if empty:
        problems.append(f"empty: {', '.join(empty)}")
    if problems:
        return False, "Required sections — " + "; ".join(problems)
    return True, f"All {len(required)} required sections present and non-empty."


def check_measurable_success_criteria(doc: Document, ctx: dict) -> tuple[bool, str]:
    section = doc.section("Success Criteria")
    if section is None:
        return False, "No Success Criteria section."
    items = section.list_items
    if not items:
        return False, "Success Criteria has no bulleted criteria."
    unmeasurable = [it for it in items if not _is_measurable(it)]
    if unmeasurable:
        preview = "; ".join(f'“{u[:60]}”' for u in unmeasurable)
        return False, f"{len(unmeasurable)}/{len(items)} criteria lack a measurable threshold: {preview}"
    return True, f"All {len(items)} success criteria state a measurable threshold."


def check_risks_owner_mitigation(doc: Document, ctx: dict) -> tuple[bool, str]:
    section = doc.section("Risks")
    if section is None:
        return False, "No Risks section."
    items = section.list_items
    if not items:
        return False, "Risks has no bulleted risks."
    bad = []
    for it in items:
        if _field_value(it, "owner") is None or _field_value(it, "mitigation") is None:
            bad.append(it)
    if bad:
        preview = "; ".join(f'“{b[:60]}”' for b in bad)
        return False, f"{len(bad)}/{len(items)} risks miss an Owner and/or Mitigation: {preview}"
    return True, f"All {len(items)} risks name an owner and a mitigation."


def check_dates_consistent(doc: Document, ctx: dict) -> tuple[bool, str]:
    dates = doc.frontmatter.get("dates") or {}
    created = _as_date(dates.get("created"))
    target = _as_date(dates.get("target"))
    if created is None or target is None:
        return False, "dates.created and dates.target must be valid ISO dates."
    if target < created:
        return False, f"target ({target}) is before created ({created})."
    return True, f"Dates consistent (created {created} → target {target})."


def check_unique_id(doc: Document, ctx: dict) -> tuple[bool, str]:
    if not doc.id:
        return False, "Document has no id."
    others = [p for p in ctx.get("id_index", {}).get(doc.id, []) if p != doc.path]
    if others:
        return False, f"id '{doc.id}' also used by: {', '.join(others)}"
    return True, f"id '{doc.id}' is unique."


def _project_code(doc: Document) -> str:
    """The project code for a document, e.g. 'AUR' from project: PRJ-001-AUR."""
    return str(doc.frontmatter.get("project", "")).split("-")[-1]


def check_items_well_formed(doc: Document, ctx: dict) -> tuple[bool, str]:
    """Every bullet in a declared item-section is a valid item
    ``**<CODE>-<TYPE>-<NNN>**``: the type matches the section, and the project
    code matches the document's project."""
    specs = ctx.get("item_sections") or []
    if not specs:
        return True, "No item sections for this kind."
    code = _project_code(doc)
    problems: list[str] = []
    total = 0
    for spec in specs:
        section = doc.section(spec["section"])
        if section is None:
            continue  # a missing section is the required-sections check's job
        for raw, m in iter_item_lines(section):
            total += 1
            if not m:
                problems.append(f'malformed item in "{spec["section"]}": “{raw[:50]}”')
                continue
            if m.group("type") != spec["prefix"]:
                problems.append(
                    f'“{m.group("id")}” in "{spec["section"]}" should be type '
                    f'{spec["prefix"]} ({code}-{spec["prefix"]}-NNN)')
            if code and m.group("project") != code:
                problems.append(
                    f'“{m.group("id")}” uses project {m.group("project")} but the '
                    f'document belongs to {code}')
    if problems:
        return False, "; ".join(problems)
    return True, f"All {total} item(s) well-formed."


_PROJECT_ID_RE = re.compile(r"^PRJ-\d{3,}-(?P<code>[A-Z]{2,6})$")


def check_project_id_format(doc: Document, ctx: dict) -> tuple[bool, str]:
    """A project.md declares a well-formed id (PRJ-NNN-CODE) whose tail matches
    its `code` field."""
    pid = str(doc.frontmatter.get("id", ""))
    code = str(doc.frontmatter.get("code", ""))
    m = _PROJECT_ID_RE.match(pid)
    if not m:
        return False, f"project id {pid!r} must match PRJ-NNN-CODE (e.g. PRJ-001-AUR)."
    if m.group("code") != code:
        return False, f"project id tail ({m.group('code')}) must equal code ({code!r})."
    return True, f"Project id {pid} is well-formed."


_RISK_FIELDS = ["Probability", "Impact", "Owner", "Response"]
_ADR_STATES = {"proposed", "accepted", "superseded", "deprecated", "rejected"}


def _items_of_prefix(doc: Document, ctx: dict, prefix: str):
    """Yield (id, text) for every well-formed item of `prefix` in the doc."""
    for spec in (ctx.get("item_sections") or []):
        if spec.get("prefix") != prefix:
            continue
        section = doc.section(spec["section"])
        if section is None:
            continue
        for _raw, m in iter_item_lines(section):
            if m:
                yield m.group("id"), m.group("text")


def check_risk_items_complete(doc: Document, ctx: dict) -> tuple[bool, str]:
    """Every RISK item names a Probability, Impact, Owner, and Response."""
    incomplete, total = [], 0
    for iid, text in _items_of_prefix(doc, ctx, "RISK"):
        total += 1
        missing = [f for f in _RISK_FIELDS if _field_value(text, f) is None]
        if missing:
            incomplete.append(f'{iid} missing {", ".join(missing)}')
    if incomplete:
        return False, "; ".join(incomplete)
    return True, f"All {total} risk(s) state probability, impact, owner, and response."


def check_adr_items_have_status(doc: Document, ctx: dict) -> tuple[bool, str]:
    """Every ADR item declares a valid Status."""
    bad, total = [], 0
    for iid, text in _items_of_prefix(doc, ctx, "ADR"):
        total += 1
        status = _field_value(text, "status")
        if status is None or status.lower() not in _ADR_STATES:
            bad.append(f"{iid} status {status!r}")
    if bad:
        return False, ("; ".join(bad)
                       + f" (expected one of: {', '.join(sorted(_ADR_STATES))})")
    return True, f"All {total} decision(s) have a valid status."


def check_raci_one_accountable(doc: Document, ctx: dict) -> tuple[bool, str]:
    """The RACI Matrix table has exactly one Accountable (A) per activity."""
    section = doc.section("RACI Matrix")
    if section is None:
        return False, "No RACI Matrix section."
    rows = [ln.strip() for ln in section.body.splitlines() if ln.strip().startswith("|")]
    data = [r for r in rows if "---" not in r][1:]  # drop header + separator
    if not data:
        return False, "RACI Matrix has no activity rows."
    problems = []
    for row in data:
        cells = [c.strip() for c in row.strip("|").split("|")]
        activity = cells[0] if cells else "?"
        a_count = sum(1 for c in cells[1:] if c.upper() == "A")
        if a_count != 1:
            problems.append(f'"{activity}" has {a_count} Accountable (need exactly 1)')
    if problems:
        return False, "; ".join(problems)
    return True, f"All {len(data)} activities have exactly one Accountable role."


def check_story_format(doc: Document, ctx: dict) -> tuple[bool, str]:
    """Every US item follows 'As a … I want … so that …'."""
    bad, total = [], 0
    for iid, text in _items_of_prefix(doc, ctx, "US"):
        total += 1
        low = text.lower()
        if not (("as a " in low or "as an " in low) and "i want" in low):
            bad.append(iid)
    if bad:
        return False, "stories not in 'As a … I want …' form: " + ", ".join(bad)
    return True, f"All {total} user story(ies) follow the standard form."


def check_measurable_exit_criteria(doc: Document, ctx: dict) -> tuple[bool, str]:
    """Every Exit Criteria bullet states a measurable threshold."""
    section = doc.section("Exit Criteria")
    if section is None:
        return False, "No Exit Criteria section."
    items = section.list_items
    if not items:
        return False, "Exit Criteria has no bulleted criteria."
    unmeasurable = [it for it in items if not _is_measurable(it)]
    if unmeasurable:
        preview = "; ".join(f'“{u[:50]}”' for u in unmeasurable)
        return False, f"{len(unmeasurable)}/{len(items)} exit criteria lack a measurable threshold: {preview}"
    return True, f"All {len(items)} exit criteria state a measurable threshold."


def check_has_mapping_table(doc: Document, ctx: dict) -> tuple[bool, str]:
    """The Field Mapping section contains a table with at least one row."""
    section = doc.section("Field Mapping")
    if section is None:
        return False, "No Field Mapping section."
    rows = [ln.strip() for ln in section.body.splitlines() if ln.strip().startswith("|")]
    data = [r for r in rows if "---" not in r][1:]
    if not data:
        return False, "Field Mapping has no mapping table rows."
    return True, f"Field Mapping table has {len(data)} row(s)."


_STEP_RE = re.compile(r"^\s*\d+\.\s")


def check_numbered_steps(doc: Document, ctx: dict) -> tuple[bool, str]:
    """Each section named in `steps_sections` has an ordered (numbered) list of
    at least two steps."""
    specs = ctx.get("steps_sections") or []
    if not specs:
        return True, "No step sections for this kind."
    problems, total = [], 0
    for name in specs:
        section = doc.section(name)
        if section is None:
            continue
        n = sum(1 for ln in section.body.splitlines() if _STEP_RE.match(ln))
        total += n
        if n < 2:
            problems.append(f'"{name}" needs at least 2 numbered steps (found {n})')
    if problems:
        return False, "; ".join(problems)
    return True, f"Step sections have {total} numbered step(s)."


def check_measurable_items(doc: Document, ctx: dict) -> tuple[bool, str]:
    """Every bullet in each section named in `measurable_sections` states a
    measurable threshold."""
    specs = ctx.get("measurable_sections") or []
    if not specs:
        return True, "No measurable sections for this kind."
    problems, total = [], 0
    for name in specs:
        section = doc.section(name)
        if section is None:
            continue
        items = section.list_items
        if not items:
            problems.append(f'"{name}" has no bulleted items')
            continue
        total += len(items)
        bad = [it for it in items if not _is_measurable(it)]
        if bad:
            problems.append(f'{len(bad)}/{len(items)} in "{name}" lack a measurable '
                            f'threshold: ' + "; ".join(f'“{b[:40]}”' for b in bad))
    if problems:
        return False, "; ".join(problems)
    return True, f"All {total} item(s) in measurable sections state a threshold."


_RISK_REF_RE = re.compile(r"\b[A-Z]{2,6}-RISK-\d+\b")


def check_references_risk(doc: Document, ctx: dict) -> tuple[bool, str]:
    """The 'Risks & Issues' section cites at least one <CODE>-RISK-### from the register."""
    section = doc.section("Risks & Issues")
    if section is None:
        return False, "No Risks & Issues section."
    refs = _RISK_REF_RE.findall(section.body)
    if not refs:
        return False, "Risks & Issues cites no <CODE>-RISK-### from the register."
    return True, f"Cites {len(set(refs))} risk(s) from the register: {', '.join(sorted(set(refs)))}."


CHECKS: dict[str, Callable[[Document, dict], tuple[bool, str]]] = {
    "frontmatter-schema": check_frontmatter_schema,
    "required-sections": check_required_sections,
    "measurable-success-criteria": check_measurable_success_criteria,
    "risks-have-owner-and-mitigation": check_risks_owner_mitigation,
    "dates-consistent": check_dates_consistent,
    "unique-id": check_unique_id,
    "items-well-formed": check_items_well_formed,
    "risk-items-complete": check_risk_items_complete,
    "adr-items-have-status": check_adr_items_have_status,
    "raci-one-accountable": check_raci_one_accountable,
    "story-format": check_story_format,
    "measurable-exit-criteria": check_measurable_exit_criteria,
    "mapping-table": check_has_mapping_table,
    "numbered-steps": check_numbered_steps,
    "measurable-items": check_measurable_items,
    "references-risk": check_references_risk,
    "project-id-format": check_project_id_format,
}


def run_structural(doc: Document, spec: dict, ctx: dict) -> CheckResult:
    """Run one structural check described by a criteria `spec` dict."""
    check_id = spec["id"]
    fn = CHECKS.get(check_id)
    blocking = bool(spec.get("blocking", True))
    if fn is None:
        return CheckResult(check_id, False, blocking,
                           f"Unknown structural check '{check_id}'.", kind="structural")
    try:
        passed, detail = fn(doc, ctx)
    except Exception as exc:  # a check crash is a failure, never a silent pass
        return CheckResult(check_id, False, blocking,
                           f"Check errored: {exc}", kind="structural")
    return CheckResult(check_id, passed, blocking, detail, kind="structural")
