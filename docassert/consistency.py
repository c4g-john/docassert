"""Cross-document consistency checks over the traceable-item graph.

Structural checks are deterministic and blocking:
  - item-id-uniqueness   : IDs unique across the repo (always blocks)
  - referential-integrity: every link target exists (always blocks)
  - required-links       : downstream items declare their upstream link
                           (blocks only when the item's doc is approved)
  - coverage             : every parent item has >=1 downstream child
                           (blocks only when the parent's doc is approved)

Semantic alignment is AI-graded and advisory (never blocks).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from . import config as config_mod
from .graph import build_graph
from .models import CheckResult
from .semantic import run_alignment

CONFIG_PATH = Path("consistency.yaml")
APPROVED_STATES = {"approved", "baselined"}


def load_config(path: str | Path = CONFIG_PATH) -> dict:
    if not Path(path).is_file():
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _approved(item) -> bool:
    return str(item.doc_status).lower() in APPROVED_STATES


# ── structural (deterministic) ─────────────────────────────────────────────
def check_unique_item_ids(graph) -> CheckResult:
    dups = graph.duplicates()
    if not dups:
        return CheckResult("item-id-uniqueness", True, True,
                           f"All {len(graph.occurrences)} item IDs are unique.")
    detail = "; ".join(f"{iid} in {', '.join(paths)}" for iid, paths in dups.items())
    return CheckResult("item-id-uniqueness", False, True,
                       f"Duplicate item IDs: {detail}")


def check_referential_integrity(graph) -> CheckResult:
    broken = []
    for item in graph.all_items():
        for relation, targets in item.links.items():
            for target in targets:
                if not graph.exists(target):
                    broken.append(f"{item.id} —{relation}→ {target} (missing)")
    if broken:
        return CheckResult("referential-integrity", False, True,
                           f"{len(broken)} broken reference(s): " + "; ".join(broken))
    return CheckResult("referential-integrity", True, True, "All references resolve.")


def check_required_links(graph, config) -> CheckResult:
    required = config.get("required_links", {})
    approved_orphans, draft_orphans = [], []
    for item in graph.all_items():
        relation = required.get(item.type)
        if relation and not item.targets(relation):
            bucket = approved_orphans if _approved(item) else draft_orphans
            bucket.append(f"{item.id} (missing '{relation}')")
    parts = []
    if approved_orphans:
        parts.append("approved items missing a required link: " + "; ".join(approved_orphans))
    if draft_orphans:
        parts.append(f"{len(draft_orphans)} draft item(s) not yet linked (ok until approved)")
    return CheckResult("required-links", not approved_orphans, True,
                       " · ".join(parts) if parts else "All required upstream links present.")


def check_coverage(graph, config) -> CheckResult:
    approved_gaps, draft_gaps = [], []
    for rule in config.get("coverage", []):
        parent_prefix, relation = rule["parent"], rule["relation"]
        by_prefix = rule.get("by_prefix")
        label = rule.get("label", f"{parent_prefix} → {by_prefix}")
        for parent in graph.by_type.get(parent_prefix, []):
            if graph.children(parent.id, relation, by_prefix):
                continue
            bucket = approved_gaps if _approved(parent) else draft_gaps
            bucket.append(f"{parent.id} ({label})")
    parts = []
    if approved_gaps:
        parts.append("approved items with no downstream coverage: " + "; ".join(approved_gaps))
    if draft_gaps:
        parts.append(f"{len(draft_gaps)} draft item(s) not yet covered (ok until approved)")
    return CheckResult("coverage", not approved_gaps, True,
                       " · ".join(parts) if parts else "All approved items are covered.")


def check_profile_completeness(documents_dir: str | Path = "documents") -> CheckResult:
    """Every profiled project must carry the documents its profile requires.

    Blocks when an *enforced* (e.g. active) project is missing a required kind,
    or names a profile that doesn't exist. Projects not yet enforced (e.g.
    proposed) surface their gaps as advisory only.
    """
    from . import status as status_mod
    report = status_mod.completeness_report(documents_dir)
    blockers, unknowns, advisories = [], [], []
    for r in report:
        if r.get("unknown"):
            unknowns.append(f"{r['id']} → unknown profile '{r['profile']}'")
        elif r["blocks"]:
            blockers.append(f"{r['id']} ({r['profile']}) missing required: "
                            + ", ".join(r["missing_required"]))
        elif r["missing_required"] or r["incomplete_required"]:
            n = len(r["missing_required"]) + len(r["incomplete_required"])
            advisories.append(f"{r['id']} ({n} not yet complete)")
    parts = []
    if blockers:
        parts.append("active projects missing required documents: " + "; ".join(blockers))
    if unknowns:
        parts.append("unknown profiles: " + "; ".join(unknowns))
    if advisories:
        parts.append(f"{len(advisories)} project(s) with advisory gaps (not enforced yet)")
    return CheckResult("profile-completeness", not blockers and not unknowns, True,
                       " · ".join(parts) if parts else
                       "All profiled projects carry their required documents.")


# ── semantic (advisory) ────────────────────────────────────────────────────
def run_alignment_checks(graph, config) -> list[CheckResult]:
    edges = []  # (prompt, parent, child, relation)
    for rule in config.get("alignment", []):
        relation, prompt = rule["relation"], rule.get("prompt", "").strip()
        for child in graph.all_items():
            for target in child.targets(relation):
                parent = graph.canonical(target)
                if parent is not None:
                    edges.append((prompt, parent, child, relation))

    if not edges:
        return []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return [CheckResult("alignment", True, False,
                            f"skipped — no ANTHROPIC_API_KEY ({len(edges)} link(s) to grade)",
                            kind="semantic", score=None)]
    return [run_alignment(f"align:{c.id}-{rel}-{p.id}", prompt, p.text, c.text)
            for prompt, p, c, rel in edges]


def run_consistency(documents_dir: str | Path = "documents",
                    config_path: str | Path | None = None,
                    with_semantic: bool = True) -> list[CheckResult]:
    graph = build_graph(documents_dir)
    cfg = load_config(config_path) if config_path is not None else config_mod.read_consistency_config()
    results = [
        check_unique_item_ids(graph),
        check_referential_integrity(graph),
        check_required_links(graph, cfg),
        check_coverage(graph, cfg),
        check_profile_completeness(documents_dir),
    ]
    if with_semantic:
        results.extend(run_alignment_checks(graph, cfg))
    return results
