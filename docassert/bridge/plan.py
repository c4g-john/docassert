"""Build the execution-bridge plan from the document graph (pure, no I/O).

Scope authority flows one way: documents -> GitHub. This module decides WHAT
should exist on the board (Features from product requirements, Stories from
approved user stories); the executor makes GitHub match it. Nothing here, or
anywhere in the bridge, writes to documents/.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..graph import build_graph
from ..loader import load

APPROVED = {"approved", "baselined"}
MARKER = "<!-- docassert-bridge: {} -->"


@dataclass
class Story:
    id: str
    text: str
    feature_id: str
    doc_path: str


@dataclass
class Feature:
    id: str
    text: str
    doc_path: str
    project: str
    stories: list[Story] = field(default_factory=list)
    acceptance: list[tuple[str, str]] = field(default_factory=list)  # (id, text)
    tests: list[str] = field(default_factory=list)                   # tc ids


@dataclass
class BridgePlan:
    projects: list[dict] = field(default_factory=list)   # {id, code, features}
    skipped: list[dict] = field(default_factory=list)    # {id, reason}

    @property
    def features(self) -> list[Feature]:
        return [f for p in self.projects for f in p["features"]]

    @property
    def stories(self) -> list[Story]:
        return [s for f in self.features for s in f.stories]

    @property
    def managed_ids(self) -> set[str]:
        return {f.id for f in self.features} | {s.id for s in self.stories}


def _repo_rel(path: str, documents_dir: Path) -> str:
    """Path relative to the docs repo root (the parent of documents_dir).

    Issue bodies link Source as {docs_url}/{doc_path}, and docs_url points at
    the docs repository. When CI checks that repository out into a
    subdirectory, load paths carry the checkout prefix; stripping down to the
    repo root keeps the links valid wherever the docs are checked out.
    """
    rel = os.path.relpath(path, documents_dir.parent)
    return path if rel.startswith("..") else Path(rel).as_posix()


def _title(item_text: str, limit: int = 64) -> str:
    """First sentence of the item text, trimmed for an issue title."""
    first = item_text.split(". ")[0].rstrip(".")
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def _anchors(documents_dir: Path) -> dict[str, dict]:
    """project id -> {code, name} for every project anchor."""
    out: dict[str, dict] = {}
    for path in sorted(documents_dir.rglob("project.md")):
        try:
            doc = load(path)
        except ValueError:
            continue
        if doc.kind == "project" and doc.id:
            out[doc.id] = {"code": str(doc.frontmatter.get("code", "")),
                           "name": str(doc.frontmatter.get("name", "")),
                           "repo": str(doc.frontmatter.get("repo", "") or "")}
    return out


def _story_docs(documents_dir: Path) -> dict[str, list]:
    """project id -> its user-story documents."""
    out: dict[str, list] = {}
    for path in sorted(documents_dir.rglob("*.md")):
        try:
            doc = load(path)
        except ValueError:
            continue
        if doc.kind == "user-story":
            proj = str(doc.frontmatter.get("project", ""))
            out.setdefault(proj, []).append(doc)
    return out


def build_bridge_plan(documents_dir: str | Path = "documents") -> BridgePlan:
    """The gate (Decision D): a project qualifies when it has a user-story
    document with approved status, and every approved story traces to an
    existing product requirement. Draft/proposed stories never reach the board.
    """
    documents_dir = Path(documents_dir)
    graph = build_graph(documents_dir)
    plan = BridgePlan()

    for proj_id, meta in _anchors(documents_dir).items():
        docs = _story_docs(documents_dir).get(proj_id, [])
        if not docs:
            plan.skipped.append({"id": proj_id, "reason": "no user-story document"})
            continue
        approved_docs = [d for d in docs
                         if str(d.frontmatter.get("status", "")).lower() in APPROVED]
        if not approved_docs:
            plan.skipped.append({"id": proj_id, "reason": "user stories not approved"})
            continue

        code = meta["code"]
        stories = [i for i in graph.by_type.get("US", [])
                   if i.project == code and i.doc_status.lower() in APPROVED]
        features: dict[str, Feature] = {}
        problems: list[str] = []
        for s in stories:
            targets = s.targets("traces")
            parents = [t for t in targets if graph.canonical(t) is not None]
            if not parents:
                problems.append(f"{s.id} has no resolvable traces link")
                continue
            for pid in parents:
                parent = graph.canonical(pid)
                if parent is None:      # filtered above; narrows the type
                    continue
                feat = features.get(parent.id)
                if feat is None:
                    feat = Feature(id=parent.id, text=parent.text,
                                   doc_path=_repo_rel(parent.doc_path,
                                                      documents_dir),
                                   project=proj_id)
                    feat.acceptance = [(a.id, a.text) for a in
                                       graph.children(parent.id, "verifies", "AC")]
                    for aid, _ in feat.acceptance:
                        feat.tests += [t.id for t in graph.children(aid, "tests", "TC")]
                    features[parent.id] = feat
                feat.stories.append(Story(
                    id=s.id, text=s.text, feature_id=parent.id,
                    doc_path=_repo_rel(s.doc_path, documents_dir)))
        if problems:
            plan.skipped.append({"id": proj_id,
                                 "reason": "; ".join(problems)})
            continue
        plan.projects.append({"id": proj_id, "code": code, "name": meta["name"],
                              "repo": meta.get("repo", ""),
                              "features": list(features.values())})
    return plan


def filter_plan(plan: BridgePlan, project: str) -> BridgePlan:
    """A plan reduced to one project (matched by id or code). Unknown ids
    yield an empty plan whose skipped list explains why."""
    key = project.strip()
    keep = [p for p in plan.projects
            if p["id"] == key or p["code"] == key]
    out = BridgePlan(projects=keep,
                     skipped=[s for s in plan.skipped if s["id"] == key])
    if not keep and not out.skipped:
        out.skipped.append({"id": key, "reason": "no such project in the plan"})
    return out


def plans_by_repo(plan: BridgePlan) -> dict[str, BridgePlan]:
    """Group a plan by each project's mapped repository (the `repo` field on
    the project anchor). Projects sharing a repo share one sub-plan, so
    reconciliation in that repo sees the union of their managed ids.
    Raises ValueError naming any project without a mapping."""
    unmapped = [p["id"] for p in plan.projects if not p.get("repo")]
    if unmapped:
        raise ValueError(
            "no repo mapping on project anchor(s): " + ", ".join(unmapped)
            + " (add `repo: OWNER/NAME` to project.md or pass --repo)")
    groups: dict[str, BridgePlan] = {}
    for proj in plan.projects:
        if proj["repo"] not in groups:
            # Each sub-plan gets its own copy: shared state across repos would
            # let one repo's run mutate another's, and skip lines print per repo.
            groups[proj["repo"]] = BridgePlan(skipped=list(plan.skipped))
        groups[proj["repo"]].projects.append(proj)
    return groups


def feature_title(f: Feature) -> str:
    return f"[{f.id}] {_title(f.text)}"


def story_title(s: Story) -> str:
    return f"[{s.id}] {_title(s.text)}"


def feature_body(f: Feature, docs_url: str | None) -> str:
    lines = [MARKER.format(f.id),
             "_Managed by the docassert bridge. Scope lives in the documents;"
             " edits here are overwritten._", "",
             f.text, "", f"**Project:** {f.project}"]
    if docs_url:
        lines.append(f"**Source:** {docs_url}/{f.doc_path}")
    if f.stories:
        lines += ["", "**Stories:**"] + [f"- {s.id}" for s in f.stories]
    if f.acceptance:
        lines += ["", "**Acceptance criteria:**"] + \
                 [f"- [ ] {aid}: {text}" for aid, text in f.acceptance]
    if f.tests:
        lines += ["", "**Verified by:** " + ", ".join(sorted(set(f.tests)))]
    return "\n".join(lines) + "\n"


def story_body(s: Story, docs_url: str | None) -> str:
    lines = [MARKER.format(s.id),
             "_Managed by the docassert bridge. Scope lives in the documents;"
             " edits here are overwritten._", "",
             s.text, "", f"**Feature:** {s.feature_id}"]
    if docs_url:
        lines.append(f"**Source:** {docs_url}/{s.doc_path}")
    return "\n".join(lines) + "\n"
