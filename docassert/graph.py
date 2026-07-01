"""Build the cross-document item graph used by the consistency engine."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from . import config
from .loader import load, parse_items
from .models import Item

DOCUMENTS_DIR = Path("documents")


class Graph:
    """All traceable items across the repo, plus a reverse (incoming) index."""

    def __init__(self) -> None:
        self.occurrences: dict[str, list[Item]] = defaultdict(list)   # id -> items
        self.by_type: dict[str, list[Item]] = defaultdict(list)       # BR/PR/… -> items
        self.by_project: dict[str, list[Item]] = defaultdict(list)    # AUR/ATL/… -> items
        self.incoming: dict[str, list[tuple[str, Item]]] = defaultdict(list)  # target -> (relation, source)

    def add(self, item: Item) -> None:
        self.occurrences[item.id].append(item)
        self.by_type[item.type].append(item)
        self.by_project[item.project].append(item)
        for relation, targets in item.links.items():
            for target in targets:
                self.incoming[target].append((relation, item))

    def exists(self, item_id: str) -> bool:
        return item_id in self.occurrences

    def canonical(self, item_id: str) -> Item | None:
        occ = self.occurrences.get(item_id)
        return occ[0] if occ else None

    def duplicates(self) -> dict[str, list[str]]:
        """id -> paths, for every id defined more than once."""
        return {iid: [it.doc_path for it in occ]
                for iid, occ in self.occurrences.items() if len(occ) > 1}

    def all_items(self) -> list[Item]:
        return [occ[0] for occ in self.occurrences.values()]

    def children(self, target_id: str, relation: str,
                 by_type: str | None = None) -> list[Item]:
        """Items that link to `target_id` via `relation` (optionally by item type)."""
        return [src for rel, src in self.incoming.get(target_id, [])
                if rel == relation and (by_type is None or src.type == by_type)]


def _item_sections_for(kind: str) -> list[dict]:
    if not config.criteria_exists(kind):
        return []
    return config.read_criteria(kind).get("item_sections", []) or []


def build_graph(documents_dir: str | Path = DOCUMENTS_DIR) -> Graph:
    graph = Graph()
    for path in sorted(Path(documents_dir).rglob("*.md")):
        try:
            doc = load(path)
        except ValueError:
            continue  # malformed frontmatter is caught by per-document validation
        for item in parse_items(doc, _item_sections_for(doc.kind or "")):
            graph.add(item)
    return graph
