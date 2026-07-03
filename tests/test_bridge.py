"""Tests for the execution bridge: plan builder (pure) + ops (fake runner)."""
import json

from docassert.bridge import build_bridge_plan, ops
from docassert.bridge.plan import feature_body, feature_title, story_body

ANCHOR = """---
kind: project
id: PRJ-001-TST
code: TST
name: Test Project
sponsor: jane.doe
status: active
---

## Overview
o.

## Scope
s.
"""

PRD = """---
kind: prd
id: TST-prd
project: PRJ-001-TST
title: T PRD
owner: jane.doe
status: approved
---

## Overview
o.

## Product Requirements
- **TST-PR-001**: The product shall do the first thing.
- **TST-PR-002**: The product shall do the second thing.

## Acceptance Criteria
- **TST-AC-001** (verifies: TST-PR-001): Given, when, then.
"""

STORIES = """---
kind: user-story
id: TST-user-story
project: PRJ-001-TST
title: T Stories
owner: jane.doe
status: {status}
---

## Overview
o.

## User Stories
- **TST-US-001** (traces: TST-PR-001): As a user, I want thing one so that value.
- **TST-US-002** (traces: TST-PR-001): As a user, I want thing one refined so that value.
- **TST-US-003** (traces: TST-PR-002): As a user, I want thing two so that value.
"""


def _tree(tmp_path, story_status="approved"):
    d = tmp_path / "documents" / "PRJ-001-TST"
    d.mkdir(parents=True)
    (d / "project.md").write_text(ANCHOR, encoding="utf-8")
    (d / "prd.md").write_text(PRD, encoding="utf-8")
    (d / "user-story.md").write_text(STORIES.format(status=story_status), encoding="utf-8")
    return tmp_path / "documents"


# ── the gate ─────────────────────────────────────────────────────────────────
def test_plan_from_approved_stories(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    assert [p["id"] for p in plan.projects] == ["PRJ-001-TST"]
    feats = {f.id: f for f in plan.features}
    assert set(feats) == {"TST-PR-001", "TST-PR-002"}
    assert [s.id for s in feats["TST-PR-001"].stories] == ["TST-US-001", "TST-US-002"]
    assert feats["TST-PR-001"].acceptance[0][0] == "TST-AC-001"
    assert plan.managed_ids == {"TST-PR-001", "TST-PR-002",
                                "TST-US-001", "TST-US-002", "TST-US-003"}


def test_gate_blocks_unapproved_stories(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path, story_status="proposed"))
    assert plan.projects == []
    assert plan.skipped[0]["reason"] == "user stories not approved"


def test_gate_blocks_missing_story_doc(tmp_path):
    docs = _tree(tmp_path)
    (docs / "PRJ-001-TST" / "user-story.md").unlink()
    plan = build_bridge_plan(docs)
    assert plan.skipped[0]["reason"] == "no user-story document"


def test_gate_blocks_untraced_story(tmp_path):
    docs = _tree(tmp_path)
    f = docs / "PRJ-001-TST" / "user-story.md"
    f.write_text(f.read_text().replace(" (traces: TST-PR-002)", ""), encoding="utf-8")
    plan = build_bridge_plan(docs)
    assert plan.projects == []
    assert "TST-US-003 has no resolvable traces link" in plan.skipped[0]["reason"]


def test_bodies_carry_marker_and_authority_note(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    f = plan.features[0]
    body = feature_body(f, "https://github.com/o/r/blob/main")
    assert f"<!-- docassert-bridge: {f.id} -->" in body
    assert "Scope lives in the documents" in body
    assert "- [ ] TST-AC-001" in body
    s = f.stories[0]
    assert f"<!-- docassert-bridge: {s.id} -->" in story_body(s, None)


def test_doc_paths_relative_to_docs_repo_root(tmp_path):
    """CI checks the docs repo out into a subdirectory; Source links must not
    carry that checkout prefix (they resolve against the docs repo root)."""
    docs = _tree(tmp_path / "pmo")
    plan = build_bridge_plan(docs)
    f = plan.features[0]
    assert f.doc_path == "documents/PRJ-001-TST/prd.md"
    assert f.stories[0].doc_path == "documents/PRJ-001-TST/user-story.md"
    body = feature_body(f, "https://github.com/o/r/blob/main")
    assert ("**Source:** https://github.com/o/r/blob/main/"
            "documents/PRJ-001-TST/prd.md") in body
    assert "/pmo/" not in body


# ── ops against a fake runner ────────────────────────────────────────────────
class FakeGh:
    """Records mutations; serves canned issue lists."""

    def __init__(self, issues=None):
        self.issues = issues or []
        self.calls: list[list[str]] = []
        self._n = 100

    def run(self, args, input_=None):
        self.calls.append(args)
        joined = " ".join(args)
        if "--paginate" in joined:
            return json.dumps(self.issues)
        if "-X" in args and "issues" in joined and "labels" not in joined \
                and "comments" not in joined and "PATCH" not in args:
            self._n += 1
            return json.dumps({"number": self._n, "node_id": f"N{self._n}",
                               "state": "open", "title": "", "body": ""})
        return "{}"

    def graphql(self, query, **vars_):
        self.calls.append(["graphql", query[:30]])
        return {}

    def api_json(self, path, *flags):
        return None


def _mk_issue(number, key, title="t", state="open", labels=()):
    return {"number": number, "node_id": f"N{number}", "state": state,
            "title": title, "body": f"<!-- docassert-bridge: {key} -->\nx",
            "labels": [{"name": lb} for lb in labels]}


def test_scaffold_creates_then_is_idempotent(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    gh = FakeGh()
    actions = ops.scaffold(plan, gh, "o/r")
    assert sum(1 for a in actions if a.startswith("created")) == 5  # 2 feat + 3 stories
    # second run: simulate full existing state with correct titles/bodies
    existing = []
    for i, f in enumerate(plan.features):
        e = _mk_issue(200 + i, f.id, feature_title(f))
        e["body"] = feature_body(f, None)
        existing.append(e)
        for j, s in enumerate(f.stories):
            e2 = _mk_issue(300 + i * 10 + j, s.id)
            from docassert.bridge.plan import story_title
            e2["title"] = story_title(s)
            e2["body"] = story_body(s, None)
            existing.append(e2)
    gh2 = FakeGh(existing)
    actions2 = ops.scaffold(plan, gh2, "o/r")
    assert not any(a.startswith(("created", "updated")) for a in actions2)


def test_reconcile_classifies_and_alerts(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    issues = [
        _mk_issue(1, "TST-US-001"),                       # matched
        {"number": 2, "node_id": "N2", "state": "open",   # no marker
         "title": "rogue idea", "body": "let's add dark mode", "labels": []},
        _mk_issue(3, "TST-US-999"),                       # orphaned
    ]
    gh = FakeGh(issues)
    lines, code = ops.reconcile(plan, gh, "o/r")
    assert code == 1
    joined = "\n".join(lines)
    assert "unverified: 1" in joined and "orphaned: 1" in joined
    label_calls = [c for c in gh.calls if any("labels[]=scope:" in a for a in c)]
    assert len(label_calls) == 2
    comment_calls = [c for c in gh.calls if "comments" in " ".join(c)]
    assert len(comment_calls) == 2


def test_reconcile_comments_only_on_transition(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    issues = [{"number": 2, "node_id": "N2", "state": "open", "title": "rogue",
               "body": "x", "labels": [{"name": "scope:unverified"}]}]
    gh = FakeGh(issues)
    lines, code = ops.reconcile(plan, gh, "o/r")
    assert code == 1                       # still drift
    comment_calls = [c for c in gh.calls if "comments" in " ".join(c)]
    assert not comment_calls               # but no re-nag


def test_reconcile_clean_board_exits_zero(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    gh = FakeGh([_mk_issue(1, "TST-US-001")])
    lines, code = ops.reconcile(plan, gh, "o/r")
    assert code == 0


def test_status_counts_closed_stories(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    issues = [
        _mk_issue(10, "TST-PR-001"),
        _mk_issue(11, "TST-US-001", state="closed"),
        _mk_issue(12, "TST-US-002"),
    ]
    gh = FakeGh(issues)
    data = ops.status(plan, gh, "o/r")
    feats = {f["id"]: f for f in data["projects"][0]["features"]}
    assert feats["TST-PR-001"]["stories_closed"] == 1
    assert feats["TST-PR-001"]["stories_total"] == 2
    assert "1/2" in ops.render_status(data)


def test_scaffold_tolerates_existing_sub_issue_link(tmp_path):
    """GitHub's duplicate-link error (observed live 2026-07-02) is success."""
    from docassert.bridge.gh import GhError

    class LinkedGh(FakeGh):
        def graphql(self, query, **vars_):
            raise GhError("gh: Failed to add sub-issue #2 to parent #1. "
                          "Issue may not contain duplicate sub-issues and "
                          "Sub issue may only have one parent")

    plan = build_bridge_plan(_tree(tmp_path))
    gh = LinkedGh()
    ops.scaffold(plan, gh, "o/r")   # must not raise


def test_add_sub_issue_still_raises_on_real_errors(tmp_path):
    from docassert.bridge.gh import GhError, add_sub_issue

    class BoomGh(FakeGh):
        def graphql(self, query, **vars_):
            raise GhError("gh: Something else entirely")

    import pytest
    with pytest.raises(GhError):
        add_sub_issue(BoomGh(), "N1", "N2")


# ── board ops ────────────────────────────────────────────────────────────────
class BoardGh(FakeGh):
    """GraphQL router for Projects v2 shapes."""

    def __init__(self, existing_fields=()):
        super().__init__()
        self.gql: list[str] = []
        self._fields = list(existing_fields)

    def graphql(self, query, **vars_):
        self.gql.append(query)
        if "viewer" in query:
            return {"viewer": {"id": "U1", "login": "tester"}}
        if "createProjectV2(" in query:
            return {"createProjectV2": {"projectV2": {"id": "P1", "number": 7,
                                                      "title": vars_.get("title")}}}
        if "projectV2(number" in query:
            nodes = [{"id": f"F-{n}", "name": n, "dataType": "TEXT"}
                     for n in self._fields]
            if "Type" in self._fields:
                for node in nodes:
                    if node["name"] == "Type":
                        node["dataType"] = "SINGLE_SELECT"
                        node["options"] = [{"id": "O1", "name": "Feature"},
                                           {"id": "O2", "name": "Story"}]
            return {"user": {"projectV2": {"id": "P1", "title": "Board",
                                           "fields": {"nodes": nodes}}}}
        if "createProjectV2Field" in query:
            self._fields.append(vars_["n"])
            return {"createProjectV2Field": {"projectV2Field": {"id": "F-new"}}}
        if "addProjectV2ItemById" in query:
            return {"addProjectV2ItemById": {"item": {"id": "I1"}}}
        if "updateProjectV2ItemFieldValue" in query:
            return {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "I1"}}}
        return {}


def test_create_project():
    from docassert.bridge import board
    gh = BoardGh()
    proj = board.create_project(gh, "Refuge for Humans")
    assert proj["number"] == 7 and proj["title"] == "Refuge for Humans"


def test_ensure_fields_creates_missing():
    from docassert.bridge import board
    gh = BoardGh(existing_fields=["Status"])
    project = board.ensure_fields(gh, "tester", 7)
    assert set(project["fields"]) >= {"Type", "Doc", "PMO Project"}


def test_scaffold_syncs_board(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    existing = []
    for i, f in enumerate(plan.features):
        e = _mk_issue(200 + i, f.id, feature_title(f))
        e["body"] = feature_body(f, None)
        existing.append(e)
        for j, s in enumerate(f.stories):
            from docassert.bridge.plan import story_title
            e2 = _mk_issue(300 + i * 10 + j, s.id, story_title(s))
            e2["body"] = story_body(s, None)
            existing.append(e2)
    gh = FakeGh(existing)
    bgh = BoardGh(existing_fields=["Type", "Doc", "PMO Project"])
    actions = ops.scaffold(plan, gh, "o/r",
                           board_cfg={"gh": bgh, "owner": "tester", "number": 7,
                                      "init": False})
    assert any("5 item(s) synced" in a for a in actions)
    adds = [q for q in bgh.gql if "addProjectV2ItemById" in q]
    assert len(adds) == 5


def test_status_includes_scope_classification(tmp_path):
    plan = build_bridge_plan(_tree(tmp_path))
    issues = [
        _mk_issue(1, "TST-US-001"),
        {"number": 2, "node_id": "N2", "state": "open", "title": "rogue",
         "body": "no marker", "labels": []},
        _mk_issue(3, "TST-US-999"),
        _mk_issue(4, "TST-US-002", state="closed"),   # closed: not scope-checked
    ]
    data = ops.status(plan, FakeGh(issues), "o/r")
    assert data["repo"] == "o/r"
    assert [i["number"] for i in data["scope"]["unverified"]] == [2]
    assert [i["doc"] for i in data["scope"]["orphaned"]] == ["TST-US-999"]
