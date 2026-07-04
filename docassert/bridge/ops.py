"""Bridge operations: scaffold, reconcile, status.

scaffold  documents -> issues/board (idempotent; never deletes)
reconcile board -> alerts (labels + one pinned scope report; never deletes)
status    board -> read-only delivery figures

The bridge never writes to documents/ — scope changes go through document PRs.
"""
from __future__ import annotations

import json
import re

from . import gh as G
from .plan import (
    MARKER,
    BridgePlan,
    feature_body,
    feature_title,
    story_body,
    story_title,
)

MARKER_RE = re.compile(r"<!-- docassert-bridge: ([A-Za-z0-9-]+) -->")
SCOPE_REPORT_KEY = "scope-report"
LABELS = {
    "bridge:feature": ("1d76db", "Feature scaffolded from a product requirement"),
    "bridge:story": ("0e8a16", "Story scaffolded from an approved user story"),
    "scope:unverified": ("d93f0b", "No matching item in the governing documents"),
    "scope:orphaned": ("b60205", "Its document item was removed or demoted"),
}


def _marker_of(issue: dict) -> str | None:
    m = MARKER_RE.search(issue.get("body") or "")
    return m.group(1) if m else None


def _index(issues: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in issues:
        key = _marker_of(i)
        if key and key not in out:          # first (oldest) wins
            out[key] = i
    return out


def _converge_duplicates(gh, repo: str, issues: list[dict]) -> tuple[list[dict], list[str]]:
    """One open issue per bridge marker: racing scaffolds may have created
    duplicates, so close every open duplicate except the lowest-numbered one
    and drop the closed ones from the working set. First writer wins."""
    from collections import defaultdict
    by_marker: dict[str, list[dict]] = defaultdict(list)
    for issue in issues:
        m = MARKER_RE.search(issue.get("body") or "")
        if m and issue.get("state") == "open":
            by_marker[m.group(1)].append(issue)
    actions: list[str] = []
    losers: set[int] = set()
    for marker, dupes in by_marker.items():
        if len(dupes) < 2:
            continue
        dupes.sort(key=lambda i: i["number"])
        for extra in dupes[1:]:
            G.update_issue(gh, repo, extra["number"], state="closed")
            G.comment(gh, repo, extra["number"],
                      f"Duplicate of #{dupes[0]['number']} (bridge marker "
                      f"{marker}); racing scaffold runs converge on the "
                      "lowest-numbered issue.")
            losers.add(extra["number"])
            actions.append(f"converged duplicate #{extra['number']} -> #{dupes[0]['number']}")
    return [i for i in issues if i["number"] not in losers], actions


def scaffold(plan: BridgePlan, gh: G.GhRunner, repo: str,
             docs_url: str | None = None,
             board_cfg: dict | None = None) -> list[str]:
    """Make the repo's issues match the plan. Returns human-readable actions.

    board_cfg (optional): {"gh": GhRunner with project scope, "owner": login,
    "number": int, "init": bool} — mirrors every managed issue onto the
    Projects v2 board with Type/Doc/PMO Project fields.
    """
    actions: list[str] = []
    for name, (color, desc) in LABELS.items():
        G.ensure_label(gh, repo, name, color, desc)

    issues = G.list_issues(gh, repo)
    issues, converge_actions = _converge_duplicates(gh, repo, issues)
    actions.extend(converge_actions)
    by_key = _index(issues)

    def ensure(key: str, title: str, body: str, label: str) -> dict:
        existing = by_key.get(key)
        if existing is None:
            created = G.create_issue(gh, repo, title, body, [label])
            created["body"] = body
            by_key[key] = created
            actions.append(f"created #{created.get('number', '?')} {title}")
            return created
        if existing.get("title") != title or (existing.get("body") or "").strip() != body.strip():
            G.update_issue(gh, repo, existing["number"], title=title, body=body)
            actions.append(f"updated #{existing['number']} {title}")
        if existing.get("state") == "closed" and key in plan.managed_ids:
            pass  # closed means delivered; scaffold never reopens
        return existing

    for f in plan.features:
        feat_issue = ensure(f.id, feature_title(f), feature_body(f, docs_url),
                            "bridge:feature")
        for s in f.stories:
            story_issue = ensure(s.id, story_title(s), story_body(s, docs_url),
                                 "bridge:story")
            pnode, cnode = feat_issue.get("node_id"), story_issue.get("node_id")
            if pnode and cnode:
                G.add_sub_issue(gh, pnode, cnode)

    if board_cfg:
        from . import board as B
        bgh = board_cfg["gh"]
        if board_cfg.get("init"):
            project = B.ensure_fields(bgh, board_cfg["owner"], board_cfg["number"])
            actions.append(f"board: fields ensured on '{project['title']}'")
        else:
            project = B.get_project(bgh, board_cfg["owner"], board_cfg["number"])
        entries = []
        for f in plan.features:
            issue = by_key.get(f.id)
            if issue and issue.get("node_id"):
                entries.append({"node_id": issue["node_id"], "doc_id": f.id,
                                "type": "Feature", "pmo_project": f.project})
            for s in f.stories:
                sissue = by_key.get(s.id)
                if sissue and sissue.get("node_id"):
                    entries.append({"node_id": sissue["node_id"], "doc_id": s.id,
                                    "type": "Story", "pmo_project": f.project})
        n = B.sync_items(bgh, project, entries)
        actions.append(f"board: {n} item(s) synced to '{project['title']}'")

    for sk in plan.skipped:
        actions.append(f"skipped {sk['id']}: {sk['reason']}")
    return actions


def reconcile(plan: BridgePlan, gh: G.GhRunner, repo: str) -> tuple[list[str], int]:
    """Police the board against the documents. Returns (report lines, exit code)."""
    for name, (color, desc) in LABELS.items():
        G.ensure_label(gh, repo, name, color, desc)

    managed = plan.managed_ids
    issues = G.list_issues(gh, repo, state="open")
    unverified, orphaned = [], []

    for issue in issues:
        key = _marker_of(issue)
        if key == SCOPE_REPORT_KEY:
            continue
        labels = {lb["name"] for lb in issue.get("labels", [])}
        number = issue["number"]

        if key is None:
            unverified.append(issue)
            if "scope:unverified" not in labels:
                gh.run(["api", f"repos/{repo}/issues/{number}/labels", "-X", "POST",
                        "-f", "labels[]=scope:unverified"])
                G.comment(gh, repo, number,
                          "**Scope check:** this issue has no matching item in the "
                          "governing documents. Scope is defined in the PMO repo; "
                          "either link it to an approved item or move the scope "
                          "change through a documents PR.")
        elif key not in managed:
            orphaned.append(issue)
            if "scope:orphaned" not in labels:
                gh.run(["api", f"repos/{repo}/issues/{number}/labels", "-X", "POST",
                        "-f", "labels[]=scope:orphaned"])
                G.comment(gh, repo, number,
                          f"**Scope check:** `{key}` no longer resolves to an "
                          "approved item in the documents (removed, renamed, or "
                          "demoted). A human should decide whether to close this "
                          "issue or restore the item.")

    lines = [f"managed items: {len(managed)}",
             f"open issues checked: {len(issues)}",
             f"unverified: {len(unverified)}", f"orphaned: {len(orphaned)}"]
    for i in unverified:
        lines.append(f"  unverified: #{i['number']} {i['title']}")
    for i in orphaned:
        lines.append(f"  orphaned: #{i['number']} {i['title']} [{_marker_of(i)}]")

    body = (MARKER.format(SCOPE_REPORT_KEY)
            + "\n_Maintained by `docassert bridge reconcile`. The documents are "
              "the authoritative scope source._\n\n```\n" + "\n".join(lines) + "\n```\n")
    report = _index(G.list_issues(gh, repo)).get(SCOPE_REPORT_KEY)
    if report is None:
        G.create_issue(gh, repo, "Scope report — docassert bridge", body, [])
    else:
        G.update_issue(gh, repo, report["number"], body=body)

    return lines, (1 if (unverified or orphaned) else 0)


def status(plan: BridgePlan, gh: G.GhRunner, repo: str) -> dict:
    """Read-only: delivery progress per feature, plus scope classification.

    Unlike reconcile, this never labels or comments; it only reports, so it is
    safe to run from the dashboard build.
    """
    issues = G.list_issues(gh, repo)
    by_key = _index(issues)
    managed = plan.managed_ids
    unverified, orphaned = [], []
    for issue in issues:
        if issue.get("state") != "open":
            continue
        key = _marker_of(issue)
        if key == SCOPE_REPORT_KEY:
            continue
        if key is None:
            unverified.append({"number": issue["number"], "title": issue["title"]})
        elif key not in managed:
            orphaned.append({"number": issue["number"], "title": issue["title"],
                             "doc": key})
    out: dict = {"repo": repo, "projects": [],
                 "scope": {"unverified": unverified, "orphaned": orphaned}}
    def facts(key):
        """Real, presentational issue facts (never fed back into derivation)."""
        issue = by_key.get(key) or {}
        return {
            "title": issue.get("title"),
            "state": issue.get("state"),
            "created_at": (issue.get("created_at") or "")[:10] or None,
            "closed_at": (issue.get("closed_at") or "")[:10] or None,
            "url": issue.get("html_url"),
            "assignee": (issue.get("assignee") or {}).get("login"),
            "labels": [lb.get("name") for lb in issue.get("labels") or []],
        }

    for p in plan.projects:
        feats = []
        for f in p["features"]:
            states = [(by_key.get(s.id) or {}).get("state") for s in f.stories]
            feats.append({
                "id": f.id,
                "issue": (by_key.get(f.id) or {}).get("number"),
                "facts": facts(f.id),
                "stories": [{"id": s.id,
                             "issue": (by_key.get(s.id) or {}).get("number"),
                             "facts": facts(s.id)} for s in f.stories],
                "stories_total": len(f.stories),
                "stories_closed": sum(1 for s in states if s == "closed"),
                "closed": (by_key.get(f.id) or {}).get("state") == "closed",
            })
        done = sum(x["stories_closed"] for x in feats)
        total = sum(x["stories_total"] for x in feats)
        out["projects"].append({"id": p["id"], "features": feats,
                                "stories_closed": done, "stories_total": total})
    return out


def render_status(data: dict) -> str:
    lines = []
    for p in data["projects"]:
        lines.append(f"{p['id']}: {p['stories_closed']}/{p['stories_total']} stories closed")
        for f in p["features"]:
            mark = "✓" if f["closed"] else " "
            lines.append(f"  [{mark}] {f['id']}: {f['stories_closed']}/{f['stories_total']}"
                         + (f" (#{f['issue']})" if f["issue"] else " (no issue)"))
    return "\n".join(lines) or "no qualifying projects"


def to_json(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"
