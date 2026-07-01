"""Derive a project status view from the documents.

Nothing here is authored: every number comes from the actual files and the
traceability graph. This is "derived status over self-reported status" — the
page computes its own RAG from real signals rather than trusting a typed field.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config as config_mod
from . import profiles as profiles_mod
from .graph import build_graph
from .loader import load
from .structural import _field_value, run_structural

DOCUMENTS_DIR = Path("documents")
APPROVED = {"approved", "baselined"}
_SEVERITY = {"low": 1, "medium": 2, "high": 3, "critical": 4}


# ── per-document validity (blocking structural checks only) ─────────────────
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


def _risks(graph, code=None):
    risks = []
    for item in graph.by_type.get("RISK", []):
        if code and item.project != code:
            continue
        prob = (_field_value(item.text, "probability") or "").lower()
        impact = (_field_value(item.text, "impact") or "").lower()
        risks.append({
            "id": item.id,
            "probability": prob or "?",
            "impact": impact or "?",
            "owner": _field_value(item.text, "owner") or "?",
            "score": _SEVERITY.get(prob, 0) * _SEVERITY.get(impact, 0),
        })
    return sorted(risks, key=lambda r: -r["score"])


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

    id_index = {}
    for d in all_docs:                       # uniqueness is always global
        id_index.setdefault(d.id, []).append(d.path)

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
        "broken_references": _broken_references(graph, code),
        "latest_report": _latest_report(docs),
        "completeness": completeness,
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
    from . import projects as projects_mod
    out = []
    for p in projects_mod.load_projects(documents_dir):
        comp = build_status(documents_dir, project=p["id"]).get("completeness")
        if comp:
            out.append({"id": p["id"], "name": p["name"], "lifecycle": p["status"], **comp})
    return out


def build_index(documents_dir=DOCUMENTS_DIR) -> dict:
    """The multi-project view: each project's derived RAG + headline signals,
    plus the whole-repo rollup."""
    from . import projects as projects_mod
    cards = []
    for p in projects_mod.load_projects(documents_dir):
        m = build_status(documents_dir, project=p["id"])
        cards.append({
            "id": p["id"], "code": p["code"], "name": p["name"],
            "sponsor": p["sponsor"], "lifecycle": p["status"],
            "rag": m["rag"],
            "total": m["counts"]["total"],
            "failing": m["counts"]["failing"],
            "risks": len(m["risks"]),
            "coverage_gaps": sum(len(c["gaps"]) for c in m["coverage"]),
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
    if coverage_gap or model["risks"] or reported in {"amber", "red"} or completeness_gap:
        return "amber"
    return "green"


# ── renderers ───────────────────────────────────────────────────────────────
_EMOJI = {"green": "🟢", "amber": "🟠", "red": "🔴"}


def render_markdown(model, summary: bool = False) -> str:
    rag = model["rag"]
    c = model["counts"]
    title = model.get("title", "Project Status")
    heading = ("## " if summary else "# ") + title
    out = [f"{heading} — {_EMOJI[rag]} {rag.upper()}", ""]
    out.append(f"_Derived from {c['total']} documents across {c['kinds']} kinds "
               f"({c['approved']} approved). Generated by `docassert status` — do not edit._")
    out += ["", "## Signals", ""]

    for cov in model["coverage"]:
        pct = round(100 * cov["covered"] / cov["total"]) if cov["total"] else 100
        mark = "🟢" if not cov["gaps"] else "🟠"
        detail = f" — gaps: {', '.join(cov['gaps'])}" if cov["gaps"] else ""
        out.append(f"- {mark} **{cov['label']}**: {cov['covered']}/{cov['total']} ({pct}%){detail}")

    comp = model.get("completeness")
    if comp and comp.get("unknown"):
        out.append(f"- 🟠 **Profile** `{comp['profile']}` not found under profiles/")
    elif comp:
        mark = "🔴" if comp["blocks"] else (
            "🟠" if (comp["missing_required"] or comp["incomplete_required"]) else "🟢")
        if comp["missing_required"]:
            detail = f" — missing: {', '.join(comp['missing_required'])}"
        elif comp["incomplete_required"]:
            detail = f" — incomplete: {', '.join(comp['incomplete_required'])}"
        else:
            detail = ""
        out.append(f"- {mark} **Required documents** ({comp['profile']}): "
                   f"{comp['required_complete']}/{comp['required_total']} complete{detail}")

    if model["broken_references"]:
        out.append(f"- 🔴 **Broken references**: {len(model['broken_references'])} "
                   f"({', '.join(model['broken_references'][:3])}…)")
    failing = [d["id"] for d in model["documents"] if not d["passing"]]
    if failing:
        out.append(f"- 🔴 **Documents failing audit**: {', '.join(failing)}")

    if model["risks"]:
        out.append(f"- 🟠 **Open risks**: {len(model['risks'])}")
        for r in model["risks"][:5]:
            out.append(f"    - `{r['id']}` — {r['probability']}/{r['impact']} · owner: {r['owner']}")

    lr = model["latest_report"]
    if lr:
        out.append(f"- ℹ️ Latest status report `{lr['id']}` ({lr['period']}) reported **{lr['rag']}**")

    if not summary:
        out += ["", "## Documents", "", "| Kind | ID | Status | Audit |", "|---|---|---|---|"]
        for d in sorted(model["documents"], key=lambda x: (x["kind"], x["id"])):
            out.append(f"| {d['kind']} | {d['id']} | {d['status']} | {'✓' if d['passing'] else '✗'} |")
    else:
        out += ["", f"<sub>Full inventory of {c['total']} documents in "
                    "[`STATUS.md`](../../blob/main/STATUS.md).</sub>"]
    return "\n".join(out) + "\n"


def render_json(model) -> str:
    return json.dumps(model, indent=2) + "\n"


_HTML_CSS = """
  :root { --bg:#0d1117; --panel:#161b22; --border:#30363d; --ink:#e6edf3;
          --muted:#8b949e; --ok:#2ea043; --amber:#d29922; --bad:#f85149; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
  main { max-width:860px; margin:0 auto; padding:40px 24px 64px; }
  header { display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:8px; }
  .rag { font-weight:700; font-size:13px; letter-spacing:.08em; color:#0d1117;
         padding:5px 12px; border-radius:999px; }
  h1 { font-size:26px; margin:0; }
  .meta { color:var(--muted); font-size:13px; margin:2px 0 30px; }
  section { margin-bottom:30px; }
  h2 { font-size:15px; text-transform:uppercase; letter-spacing:.05em;
       color:var(--muted); border-bottom:1px solid var(--border); padding-bottom:8px; }
  .sig { margin:12px 0; }
  .sig-h { display:flex; justify-content:space-between; font-size:14px; margin-bottom:5px; }
  .bar { height:8px; background:var(--border); border-radius:4px; overflow:hidden; }
  .bar-f { height:100%; background:var(--ok); border-radius:4px; }
  ul { padding-left:18px; } li { margin:4px 0; }
  code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:13px;
         background:#21262d; padding:1px 5px; border-radius:4px; }
  table { width:100%; border-collapse:collapse; font-size:13.5px; }
  th,td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:600; }
  td.ok { color:var(--ok); } td.bad { color:var(--bad); font-weight:700; }
  footer { color:var(--muted); font-size:12px; margin-top:36px; border-top:1px solid var(--border); padding-top:14px; }
  .back { display:inline-block; color:var(--muted); text-decoration:none; font-size:13px; margin-bottom:14px; }
  .back:hover { color:var(--ink); }
"""

_INDEX_CSS = """
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:16px; }
  a.card { display:block; background:var(--panel); border:1px solid var(--border);
           border-radius:10px; padding:18px; text-decoration:none; color:var(--ink);
           transition:border-color .15s, transform .15s; }
  a.card:hover { border-color:var(--muted); transform:translateY(-2px); }
  .card-h { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
  .dot { width:10px; height:10px; border-radius:50%; }
  .rag-t { font-size:12px; font-weight:700; letter-spacing:.06em; }
  .code { margin-left:auto; font:12px ui-monospace,SFMono-Regular,Menlo,monospace;
          background:#21262d; color:var(--muted); padding:2px 7px; border-radius:5px; }
  .name { font-size:16px; font-weight:600; margin-bottom:3px; }
  .card .pid { color:var(--muted); font-size:12px;
               font-family:ui-monospace,SFMono-Regular,Menlo,monospace; margin-bottom:8px; }
  .sponsor { font-size:13px; color:var(--muted); margin-bottom:10px; }
  .stats { font-size:12.5px; color:var(--muted); border-top:1px solid var(--border); padding-top:8px; }
"""


def render_html(model) -> str:
    import datetime
    import html as _h
    rag = model["rag"]
    c = model["counts"]
    color = {"green": "var(--ok)", "amber": "var(--amber)", "red": "var(--bad)"}[rag]
    bar_color = {"green": "var(--ok)", "amber": "var(--amber)", "red": "var(--bad)"}[rag]
    def esc(s):
        return _h.escape(str(s))

    coverage = "".join(
        f'<div class="sig"><div class="sig-h"><span>{esc(cov["label"])}</span>'
        f'<span>{cov["covered"]}/{cov["total"]}'
        + (f' · gaps: {esc(", ".join(cov["gaps"]))}' if cov["gaps"] else "")
        + '</span></div><div class="bar"><div class="bar-f" style="width:'
        f'{(100 * cov["covered"] // cov["total"]) if cov["total"] else 100}%'
        + (";background:var(--amber)" if cov["gaps"] else "") + '"></div></div></div>'
        for cov in model["coverage"])

    risks = "".join(
        f'<li><code>{esc(r["id"])}</code> — {esc(r["probability"])}/{esc(r["impact"])}'
        f' · owner {esc(r["owner"])}</li>' for r in model["risks"]) or "<li>None open.</li>"

    problems = ""
    if model["broken_references"]:
        problems += ("<section><h2>Broken references</h2><ul>"
                     + "".join(f"<li><code>{esc(b)}</code></li>" for b in model["broken_references"])
                     + "</ul></section>")
    failing = [d for d in model["documents"] if not d["passing"]]
    if failing:
        problems += ("<section><h2>Documents failing audit</h2><ul>"
                     + "".join(f'<li><code>{esc(d["id"])}</code></li>' for d in failing)
                     + "</ul></section>")

    rows = "".join(
        f'<tr><td>{esc(d["kind"])}</td><td><code>{esc(d["id"])}</code></td>'
        f'<td>{esc(d["status"])}</td>'
        f'<td class="{"ok" if d["passing"] else "bad"}">{"✓" if d["passing"] else "✗"}</td></tr>'
        for d in sorted(model["documents"], key=lambda x: (x["kind"], x["id"])))

    lr = model["latest_report"]
    report = (f'<code>{esc(lr["id"])}</code> ({esc(lr["period"])}) → reported <b>{esc(lr["rag"])}</b>'
              if lr else "None on record.")
    gen = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    comp = model.get("completeness")
    document_set = ""
    if comp and comp.get("unknown"):
        document_set = (f'<section><h2>Document set</h2><p style="color:var(--bad)">'
                        f'Profile <code>{esc(comp["profile"])}</code> not found under profiles/.</p></section>')
    elif comp:
        _st = {"complete": ("var(--ok)", "complete"),
               "incomplete": ("var(--amber)", "incomplete"),
               "missing": ("var(--bad)", "missing")}

        def _row(item, required):
            col, lab = _st[item["state"]]
            if item["state"] == "missing" and not required:
                col, lab = "var(--muted)", "not added"
            return (f'<tr><td><code>{esc(item["kind"])}</code></td>'
                    f'<td style="color:{col};font-weight:600;">{lab}</td></tr>')

        req_rows = "".join(_row(i, True) for i in comp["required"])
        rec_rows = "".join(_row(i, False) for i in comp["recommended"])
        sep = ('<tr><td colspan="2" style="color:var(--muted);border:0;padding:14px 10px 4px;'
               'font-size:11px;text-transform:uppercase;letter-spacing:.05em;">Recommended</td></tr>'
               if rec_rows else "")
        if comp["blocks"]:
            note = (f'<p style="color:var(--bad);font-size:13px;margin:0 0 10px;">Missing required: '
                    f'<code>{esc(", ".join(comp["missing_required"]))}</code> — blocks release '
                    f'while <code>{esc(comp["enforce_when"])}</code>.</p>')
        elif comp["missing_required"] or comp["incomplete_required"]:
            note = (f'<p style="color:var(--amber);font-size:13px;margin:0 0 10px;">Advisory until '
                    f'the project is <code>{esc(comp["enforce_when"])}</code>.</p>')
        else:
            note = ""
        document_set = (f'<section><h2>Document set · {esc(comp["profile"])} '
                        f'({comp["required_complete"]}/{comp["required_total"]} required complete)</h2>'
                        f'{note}<table><thead><tr><th>Kind</th><th>State</th></tr></thead>'
                        f'<tbody>{req_rows}{sep}{rec_rows}</tbody></table></section>')

    title = esc(model.get("title", "Project Status"))
    pid = model.get("project")
    back = '<a class="back" href="index.html">← all projects</a>' if pid else ""
    scope = f" · <code>{esc(pid)}</code>" if pid else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — {rag.upper()}</title>
<style>{_HTML_CSS}
  .bar-f {{ background:{bar_color}; }}</style></head>
<body><main>
  {back}
  <header>
    <span class="rag" style="background:{color}">{rag.upper()}</span>
    <h1>{title}</h1>
  </header>
  <p class="meta">Derived from {c['total']} documents · {c['kinds']} kinds ·
    {c['approved']} approved{scope} · generated {gen}. Do not edit — regenerated from the documents.</p>
  <section><h2>Traceability coverage</h2>{coverage}</section>
  {document_set}
  {problems}
  <section><h2>Open risks ({len(model['risks'])})</h2><ul>{risks}</ul></section>
  <section><h2>Latest status report</h2><p>{report}</p></section>
  <section><h2>Documents ({c['total']})</h2>
    <table><thead><tr><th>Kind</th><th>ID</th><th>Status</th><th>Audit</th></tr></thead>
    <tbody>{rows}</tbody></table></section>
  <footer>Generated by <code>docassert status</code> from the documents in this repository.</footer>
</main></body></html>
"""


_RAG_COLOR = {"green": "var(--ok)", "amber": "var(--amber)", "red": "var(--bad)"}


def _index_card(p, esc) -> str:
    dot = _RAG_COLOR[p["rag"]]

    def plural(n, word):
        return f"{n} {word}" + ("s" if n != 1 else "")

    stats = [plural(p["total"], "doc")]
    comp = p.get("completeness")
    if comp and not comp.get("unknown"):
        stats.append(f'{comp["required_complete"]}/{comp["required_total"]} required')
    if p["risks"]:
        stats.append(plural(p["risks"], "open risk"))
    if p["coverage_gaps"]:
        stats.append(plural(p["coverage_gaps"], "coverage gap"))
    if p["failing"]:
        stats.append(plural(p["failing"], "failing doc"))
    if p["broken"]:
        stats.append(plural(p["broken"], "broken ref"))

    return (f'<a class="card" href="{esc(p["id"])}.html">'
            f'<div class="card-h"><span class="dot" style="background:{dot}"></span>'
            f'<span class="rag-t" style="color:{dot}">{esc(p["rag"].upper())}</span>'
            f'<span class="code">{esc(p["code"])}</span></div>'
            f'<div class="name">{esc(p["name"])}</div>'
            f'<div class="pid">{esc(p["id"])} · {esc(p["lifecycle"])}</div>'
            f'<div class="sponsor">Sponsor: {esc(p["sponsor"])}</div>'
            f'<div class="stats">{" · ".join(esc(s) for s in stats)}</div></a>')


def render_index_markdown(index) -> str:
    """A portfolio table: one row per project with its derived RAG."""
    overall = index["overall"]["rag"]
    out = [f"# Projects — {_EMOJI[overall]} {overall.upper()}", "",
           "| Project | Code | RAG | Docs | Required | Open risks | Sponsor |",
           "|---|---|---|---|---|---|---|"]
    for p in index["projects"]:
        comp = p.get("completeness")
        required = (f"{comp['required_complete']}/{comp['required_total']} ({comp['profile']})"
                    if comp and not comp.get("unknown") else "—")
        out.append(
            f"| {p['name']} | `{p['code']}` | {_EMOJI[p['rag']]} {p['rag'].upper()} "
            f"| {p['total']} | {required} | {p['risks']} | {p['sponsor']} |")
    return "\n".join(out) + "\n"


def render_index_html(index) -> str:
    """The multi-project landing page: one linked RAG card per project."""
    import datetime
    import html as _h
    def esc(s):
        return _h.escape(str(s))

    overall = index["overall"]["rag"]
    ocolor = _RAG_COLOR[overall]
    gen = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = "".join(_index_card(p, esc) for p in index["projects"])
    n = len(index["projects"])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PMO as Code — Projects</title>
<style>{_HTML_CSS}{_INDEX_CSS}</style></head>
<body><main>
  <header>
    <span class="rag" style="background:{ocolor}">{overall.upper()}</span>
    <h1>Projects</h1>
  </header>
  <p class="meta">{n} project(s) · derived portfolio health · generated {gen}.
    Each card's RAG is computed from that project's own documents.</p>
  <section class="grid">{cards}</section>
  <footer>Generated by <code>docassert pages</code> from the documents in this repository.</footer>
</main></body></html>
"""
