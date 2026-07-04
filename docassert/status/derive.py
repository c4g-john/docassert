"""Derive project and portfolio status from the documents (the model layer).

Pure computation: reads the document graph and returns plain dicts. Rendering
lives in docassert.status.render.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import config as config_mod
from .. import profiles as profiles_mod
from ..graph import build_graph
from ..loader import load
from ..structural import _field_value, run_structural

DOCUMENTS_DIR = Path("documents")
APPROVED = {"approved", "baselined"}
_SEVERITY = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _doc_passes(doc, id_index) -> bool:
    kind = doc.kind or ""
    if not config_mod.criteria_exists(kind):
        return True
    criteria = config_mod.read_criteria(kind)
    try:
        schema = config_mod.read_schema(kind)
    except FileNotFoundError:
        schema = {}
    ctx = {
        "schema": schema,
        "required_sections": criteria.get("required_sections", []),
        "item_sections": criteria.get("item_sections", []),
        "steps_sections": criteria.get("steps_sections", []),
        "measurable_sections": criteria.get("measurable_sections", []),
        "id_index": id_index,
    }
    for spec in criteria.get("checks", []):
        if spec.get("type") == "structural":
            if run_structural(doc, spec, ctx).is_blocking_failure:
                return False
    return True


# ── signal extractors ───────────────────────────────────────────────────────
# `code` optionally scopes a signal to one project (by item project code, e.g.
# "AUR"). The graph itself stays global so cross-project link targets resolve.
def _coverage(graph, config, code=None):
    out = []
    for rule in config.get("coverage", []):
        parent_prefix, relation = rule["parent"], rule["relation"]
        by_prefix = rule.get("by_prefix")
        parents = graph.by_type.get(parent_prefix, [])
        if code:
            parents = [p for p in parents if p.project == code]
        covered = [p for p in parents if graph.children(p.id, relation, by_prefix)]
        out.append({
            "label": rule.get("label", f"{parent_prefix} → {by_prefix}"),
            "covered": len(covered),
            "total": len(parents),
            "gaps": [p.id for p in parents if p not in covered],
        })
    return out


_RISK_FIELD_RE = re.compile(
    r"\s*(?:Probability|Impact|Owner|Response)\s*:", re.IGNORECASE)


def _risks(graph, code=None):
    risks = []
    for item in graph.by_type.get("RISK", []):
        if code and item.project != code:
            continue
        prob = (_field_value(item.text, "probability") or "").lower()
        impact = (_field_value(item.text, "impact") or "").lower()
        # The description is the item text up to the first metadata field;
        # the response runs from its label to the end (it may hold clauses
        # that _field_value would truncate at a sentence break).
        m = _RISK_FIELD_RE.search(item.text)
        description = (item.text[:m.start()] if m else item.text).strip()
        rm = re.search(r"Response\s*:\s*(.+)$", item.text,
                       re.IGNORECASE | re.DOTALL)
        raw = (_field_value(item.text, "status") or "open").lower()
        disposition = raw if raw in {"open", "mitigated", "accepted",
                                     "closed"} else "open"
        risks.append({
            "id": item.id,
            "description": description,
            "threatens": item.links.get("threatens", []),
            "probability": prob or "?",
            "impact": impact or "?",
            "owner": _field_value(item.text, "owner") or "?",
            "response": rm.group(1).strip() if rm else "",
            "disposition": disposition,
            "score": _SEVERITY.get(prob, 0) * _SEVERITY.get(impact, 0),
        })
    # open risks first, then by severity; dispositioned risks stay as record
    return sorted(risks, key=lambda r: (r["disposition"] != "open",
                                        -r["score"]))


def _broken_references(graph, code=None):
    broken = []
    for item in graph.all_items():
        if code and item.project != code:
            continue
        for relation, targets in item.links.items():
            for target in targets:
                if not graph.exists(target):
                    broken.append(f"{item.id} —{relation}→ {target}")
    return broken


_MS_RE = re.compile(r"^(?P<label>.+?)[:\u2014\u2013-]\s*(?P<date>\d{4}-\d{2}-\d{2})\.?\s*$")


def _milestones(docs):
    """Dated charter milestones as temporal facts (never completion claims)."""
    import datetime
    today = datetime.date.today()
    out = []
    for d in docs:
        if d.kind != "charter":
            continue
        section = d.section("Milestones")
        if section is None:
            continue
        for bullet in section.list_items:
            m = _MS_RE.match(bullet.strip())
            if not m:
                continue
            try:
                due = datetime.date.fromisoformat(m.group("date"))
            except ValueError:
                continue
            out.append(_ms_entry(m.group("label").strip(), due, today))
    for d in docs:
        if d.kind != "charter":
            continue
        target = (d.frontmatter.get("dates") or {}).get("target")
        if target:
            try:
                due = (target if isinstance(target, datetime.date)
                       else datetime.date.fromisoformat(str(target)))
                if not any(x["date"] == due.isoformat() for x in out):
                    out.append(_ms_entry("Charter target", due, today))
            except (TypeError, ValueError):
                pass
    return sorted(out, key=lambda x: x["date"])


def _ms_entry(label, due, today):
    delta = (due - today).days
    return {"label": label, "date": due.isoformat(), "days": delta,
            "when": ("today" if delta == 0 else
                     "elapsed" if delta < 0 else "upcoming")}


def _operations(docs):
    """Operations documents with their review state."""
    import datetime
    out = []
    for d in docs:
        if d.kind != "operations":
            continue
        raw = d.frontmatter.get("review_by")
        try:
            due = (raw if isinstance(raw, datetime.date)
                   else datetime.date.fromisoformat(str(raw)))
            fresh = due >= datetime.date.today()
            due_s = due.isoformat()
        except (TypeError, ValueError):
            fresh, due_s = False, str(raw)
        out.append({"id": d.id, "review_by": due_s, "fresh": fresh})
    return out


def _latest_report(docs):
    reports = [d for d in docs if d.kind == "status-report"]
    if not reports:
        return None
    reports.sort(key=lambda d: str(d.frontmatter.get("period", "")), reverse=True)
    top = reports[0]
    return {
        "id": top.id,
        "period": str(top.frontmatter.get("period", "")),
        "rag": str(top.frontmatter.get("rag", "")).lower(),
    }


# ── the model + derived RAG ─────────────────────────────────────────────────
def build_status(documents_dir=DOCUMENTS_DIR, project: str | None = None) -> dict:
    """Derive the status model for the whole repo, or for one project.

    `project` is a canonical project id (PRJ-NNN-CODE). When given, documents,
    coverage, risks, broken references and the latest report are all scoped to
    that project; the graph stays global so cross-project targets still resolve.
    """
    all_docs = [load(p) for p in sorted(Path(documents_dir).rglob("*.md"))]
    graph = build_graph(documents_dir)
    cfg = config_mod.read_consistency_config()

    code = project.split("-")[-1] if project else None
    if project:
        docs = [d for d in all_docs
                if d.frontmatter.get("project") == project
                or (d.kind == "project" and d.id == project)]
    else:
        docs = all_docs

    id_index: dict[str, list[str]] = {}
    for d in all_docs:                       # uniqueness is always global
        id_index.setdefault(d.id or "", []).append(d.path)

    documents = [{
        "kind": d.kind,
        "id": d.id,
        "title": d.frontmatter.get("title", d.id),
        "status": str(d.frontmatter.get("status", "draft")),
        "passing": _doc_passes(d, id_index),
    } for d in docs]

    completeness = None
    if project:
        anchor = next((d for d in docs if d.kind == "project"), None)
        title = str(anchor.frontmatter.get("name", project)) if anchor else project
        if anchor is not None:
            completeness = _completeness_for(anchor, documents)
    else:
        title = "Project Status"

    model = {
        "project": project,
        "title": title,
        "documents": documents,
        "counts": {
            "total": len(documents),
            "kinds": len({d["kind"] for d in documents}),
            "approved": sum(1 for d in documents if d["status"] in APPROVED),
            "failing": sum(1 for d in documents if not d["passing"]),
        },
        "coverage": _coverage(graph, cfg, code),
        "risks": _risks(graph, code),
        "operations": _operations(docs),
        "milestones": _milestones(docs),
        "broken_references": _broken_references(graph, code),
        "latest_report": _latest_report(docs),
        "completeness": completeness,
        "risk_amber_score": int(cfg.get("risk_amber_score", 6) or 0),
    }
    model["rag"] = derive_rag(model)
    return model


def _completeness_for(anchor, documents: list[dict]) -> dict | None:
    """Assess a project's documents against the profile its anchor declares."""
    prof_name = anchor.frontmatter.get("profile")
    if not prof_name:
        return None
    profile = profiles_mod.load_profile(prof_name)
    if profile is None:
        return profiles_mod.unknown(prof_name)
    return profiles_mod.completeness(
        profile, documents, str(anchor.frontmatter.get("status", "")))


def completeness_report(documents_dir=DOCUMENTS_DIR) -> list[dict]:
    """Per-project completeness for every profiled project (used by the
    blocking profile-completeness consistency check)."""
    from .. import projects as projects_mod
    out = []
    for p in projects_mod.load_projects(documents_dir):
        comp = build_status(documents_dir, project=p["id"]).get("completeness")
        if comp:
            out.append({"id": p["id"], "name": p["name"], "lifecycle": p["status"], **comp})
    return out


def _next_dated(m) -> str | None:
    """The nearest upcoming dated marker (milestone or operations review)."""
    import datetime
    cands = [x["date"] for x in m.get("milestones", []) if x["days"] >= 0]
    for o in m.get("operations", []):
        try:
            if datetime.date.fromisoformat(o["review_by"]) >= datetime.date.today():
                cands.append(o["review_by"])
        except ValueError:
            pass
    return min(cands) if cands else None


def build_index(documents_dir=DOCUMENTS_DIR) -> dict:
    """The multi-project view: each project's derived RAG + headline signals,
    plus the whole-repo rollup."""
    from .. import projects as projects_mod
    cards = []
    for p in projects_mod.load_projects(documents_dir):
        m = build_status(documents_dir, project=p["id"])
        cards.append({
            "id": p["id"], "code": p["code"], "name": p["name"],
            "sponsor": p["sponsor"], "lifecycle": p["status"],
            "rag": m["rag"],
            "total": m["counts"]["total"],
            "failing": m["counts"]["failing"],
            "risks": len([r for r in m["risks"] if r.get("disposition", "open") == "open"]),
            "coverage_gaps": sum(len(c["gaps"]) for c in m["coverage"]),
            "coverage_pct": (round(100 * sum(c["covered"] for c in m["coverage"])
                                   / max(1, sum(c["total"] for c in m["coverage"])))
                             if any(c["total"] for c in m["coverage"]) else 100),
            "next": _next_dated(m),
            "broken": len(m["broken_references"]),
            "completeness": m.get("completeness"),
        })
    return {"projects": cards, "overall": build_status(documents_dir)}


def derive_rag(model) -> str:
    """Red = something is objectively broken. Amber = carrying risk or
    incompleteness. Green = clean."""
    comp = model.get("completeness")
    approved_failing = any(not d["passing"] for d in model["documents"]
                           if d["status"] in APPROVED)
    if approved_failing or model["broken_references"] or (comp and comp["blocks"]):
        return "red"
    coverage_gap = any(c["gaps"] for c in model["coverage"])
    reported = (model["latest_report"] or {}).get("rag")
    completeness_gap = bool(comp and (comp["missing_required"] or comp["incomplete_required"]
                                      or comp["recommended_gaps"] or comp.get("unknown")))
    threshold = model.get("risk_amber_score", 6)
    open_risks = [r for r in model["risks"]
                  if r.get("disposition", "open") == "open"
                  and (threshold == 0 or r.get("score", 0) >= threshold)]
    stale_ops = [o for o in model.get("operations", []) if not o["fresh"]]
    if (coverage_gap or open_risks or stale_ops
            or reported in {"amber", "red"} or completeness_gap):
        return "amber"
    return "green"


# ── renderers ───────────────────────────────────────────────────────────────
