"""Load and parse a business document into frontmatter + sections."""
from __future__ import annotations

import re
from pathlib import Path

import frontmatter
import yaml

from .models import Document, Item, Section

# A traceable item bullet, e.g.
#   **AUR-PR-014** (traces: AUR-BR-001): The flow shall be self-serve.
# The id is <CODE>-<TYPE>-<NNN>: project code, item type, number.
ITEM_RE = re.compile(
    r"^\*\*(?P<id>(?P<project>[A-Z]{2,6})-(?P<type>[A-Z]{2,6})-\d+)\*\*"   # **CODE-TYPE-123**
    r"(?:\s*\((?P<links>[^)]*)\))?"                                          # optional (relation: id, …)
    r"\s*:\s*(?P<text>.+)$"                                                  # : text
)


def parse_link_clause(clause: str) -> dict[str, list[str]]:
    """Parse `traces: BR-001, BR-002; verifies: FR-3` -> {relation: [ids]}."""
    links: dict[str, list[str]] = {}
    for group in (clause or "").split(";"):
        if ":" not in group:
            continue
        rel, ids = group.split(":", 1)
        rel = rel.strip().lower()
        id_list = [i.strip() for i in ids.split(",") if i.strip()]
        if rel and id_list:
            links.setdefault(rel, []).extend(id_list)
    return links


def parse_sections(body: str) -> dict[str, Section]:
    """Split a markdown body into H2 (`## `) sections, preserving order."""
    sections: dict[str, Section] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_title is not None:
            sections[current_title] = Section(
                title=current_title, body="\n".join(current_lines).strip()
            )

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(line)
    flush()
    return sections


def load(path: str | Path) -> Document:
    """Parse a document file. Raises ValueError on malformed frontmatter."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(text)
    except yaml.YAMLError as exc:  # malformed YAML frontmatter
        raise ValueError(f"{path}: invalid YAML frontmatter: {exc}") from exc

    return Document(
        path=str(path),
        frontmatter=dict(post.metadata),
        sections=parse_sections(post.content),
        raw_body=post.content,
    )


def load_criteria(path: str | Path) -> dict:
    """Load a criteria YAML file (e.g. criteria/charter.criteria.yaml)."""
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def iter_item_lines(section: Section):
    """Yield (raw_bullet, match_or_None) for each bullet in an item section."""
    for raw in section.list_items:
        yield raw, ITEM_RE.match(raw)


def parse_items(doc: Document, item_sections: list[dict]) -> list[Item]:
    """Extract traceable items from a document per its criteria item_sections.

    Each entry in `item_sections` is {"section": <title>, "prefix": <PREFIX>}.
    Bullets that don't parse are skipped here; the `items-well-formed`
    structural check is what flags them.
    """
    status = str(doc.frontmatter.get("status", "draft"))
    items: list[Item] = []
    for spec in item_sections or []:
        section = doc.section(spec["section"])
        if section is None:
            continue
        for _raw, m in iter_item_lines(section):
            if not m:
                continue
            items.append(Item(
                id=m.group("id"),
                project=m.group("project"),
                type=m.group("type"),
                text=m.group("text").strip(),
                links=parse_link_clause(m.group("links") or ""),
                doc_path=doc.path,
                doc_kind=doc.kind or "",
                doc_status=status,
                section=spec["section"],
            ))
    return items
