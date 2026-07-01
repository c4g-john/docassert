"""Scaffold new documents from the templates (`docassert new`).

Fills a kind's template with the right identity — `project:`, a namespaced
`id:` (AUR-brd), and for project anchors an auto-numbered PRJ-NNN-CODE — and
suggests the next free item ids so authoring starts from a valid document
instead of a hand-edited copy.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from . import config
from .graph import build_graph
from .projects import load_projects

PROJECT_ID_RE = re.compile(r"^PRJ-(?P<seq>\d{3,})-(?P<code>[A-Z]{2,6})$")
_ITEM_NUM_RE = re.compile(r"-(\d+)$")


def _set_field(text: str, field: str, value: str) -> str:
    """Set a frontmatter field, replacing its line (comments and all) if present,
    else inserting it right after `kind:`."""
    lines = text.split("\n")
    end = lines.index("---", 1)
    for i in range(1, end):
        if re.match(rf"{field}\s*:", lines[i]):
            lines[i] = f"{field}: {value}"
            return "\n".join(lines)
    for i in range(1, end):
        if re.match(r"kind\s*:", lines[i]):
            lines.insert(i + 1, f"{field}: {value}")
            return "\n".join(lines)
    lines.insert(1, f"{field}: {value}")
    return "\n".join(lines)


def _read_template(kind: str) -> str:
    path = config.template_path(kind)
    if path is None:
        kinds = ", ".join(config.available_kinds())
        raise ValueError(f"unknown kind '{kind}' (available: {kinds})")
    return path.read_text(encoding="utf-8")


def _next_project_id(code: str, anchors: list[dict]) -> str:
    seqs = [int(m.group("seq")) for a in anchors
            if (m := PROJECT_ID_RE.match(a["id"]))]
    return f"PRJ-{max(seqs, default=0) + 1:03d}-{code}"


def _item_hints(kind: str, code: str, documents_dir: str | Path) -> list[str]:
    """Next free item id per item type the kind declares (e.g. AUR-BR-003)."""
    specs = config.read_criteria(kind).get("item_sections", []) or []
    if not specs:
        return []
    graph = build_graph(documents_dir)
    hints = []
    for spec in specs:
        type_ = spec["prefix"]
        nums = [int(m.group(1)) for item in graph.by_type.get(type_, [])
                if item.project == code and (m := _ITEM_NUM_RE.search(item.id))]
        hints.append(f"{code}-{type_}-{max(nums, default=0) + 1:03d}")
    return hints


def new_document(kind: str, documents_dir: str | Path = "documents",
                 project: str | None = None, code: str | None = None,
                 name: str | None = None, out: str | Path | None = None,
                 ) -> tuple[Path, list[str]]:
    """Create a document of `kind` from its template. Returns (path, notes)."""
    docs = Path(documents_dir)
    text = _read_template(kind)
    anchors = load_projects(docs) if docs.is_dir() else []
    notes: list[str] = []

    if kind == "project":
        if project:
            m = PROJECT_ID_RE.match(project)
            if not m:
                raise ValueError(f"project id {project!r} must match PRJ-NNN-CODE (e.g. PRJ-001-AUR)")
            pid, pcode = project, m.group("code")
        elif code:
            if not re.fullmatch(r"[A-Z]{2,6}", code):
                raise ValueError(f"code {code!r} must be 2–6 uppercase letters")
            pid, pcode = _next_project_id(code, anchors), code
        else:
            raise ValueError("new project needs --project PRJ-NNN-CODE or --code CODE")
        clash = [a["id"] for a in anchors if a["id"] == pid or a["code"] == pcode]
        if clash:
            raise ValueError(f"project id/code already taken by {', '.join(clash)}")
        text = _set_field(text, "id", pid)
        text = _set_field(text, "code", pcode)
        if name:
            text = _set_field(text, "name", name)
        dest = Path(out) if out else docs / pid / "project.md"
    else:
        if not project:
            raise ValueError(f"new {kind} needs --project PRJ-NNN-CODE (the owning project)")
        anchor = next((a for a in anchors if a["id"] == project), None)
        if anchor:
            pcode = anchor["code"]
        else:
            m = PROJECT_ID_RE.match(project)
            if not m:
                raise ValueError(f"project id {project!r} must match PRJ-NNN-CODE")
            pcode = m.group("code")
            notes.append(f"no project.md anchor for {project} yet — "
                         f"create it with: docassert new project --project {project}")
        today = dt.date.today().isoformat()
        if kind == "status-report":
            doc_id = f"{pcode}-status-{today}"
            text = _set_field(text, "period", today)
            default_dest = docs / project / "status-reports" / f"{today}.md"
        else:
            doc_id = f"{pcode}-{kind}"
            default_dest = docs / project / f"{kind}.md"
        text = _set_field(text, "id", doc_id)
        text = _set_field(text, "project", project)
        dest = Path(out) if out else default_dest
        notes.extend(f"next item id: {h}" for h in _item_hints(kind, pcode, docs))

    if dest.exists():
        raise FileExistsError(f"{dest} already exists — refusing to overwrite")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest, notes
