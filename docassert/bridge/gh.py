"""Thin wrapper around the GitHub CLI for the bridge (injectable for tests).

All GitHub access goes through `gh` so token handling stays with gh/Actions
and docassert gains no HTTP dependencies. Every mutation the bridge performs
funnels through GhRunner, which dry-run mode replaces with a recorder.
"""
from __future__ import annotations

import json
import subprocess


class GhError(RuntimeError):
    pass


class GhRunner:
    """Executes gh commands. Tests substitute a fake with the same interface."""

    def run(self, args: list[str], input_: str | None = None) -> str:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True,
                              input=input_)
        if proc.returncode != 0:
            raise GhError(proc.stderr.strip() or f"gh {' '.join(args)} failed")
        return proc.stdout

    def api_json(self, path: str, *flags: str):
        out = self.run(["api", path, *flags])
        return json.loads(out) if out.strip() else None

    def graphql(self, query: str, **variables) -> dict:
        args = ["api", "graphql", "-f", f"query={query}"]
        for k, v in variables.items():
            args += (["-F", f"{k}={v}"] if isinstance(v, int)
                     else ["-f", f"{k}={v}"])
        data = json.loads(self.run(args))
        if data.get("errors"):
            raise GhError(json.dumps(data["errors"])[:400])
        return data["data"]


class DryRunner(GhRunner):
    """Reads pass through; mutations are recorded, not executed."""

    MUTATING = ("-X POST", "-X PATCH", "-X PUT", "-X DELETE", "mutation")

    def __init__(self) -> None:
        self.planned: list[str] = []

    def run(self, args: list[str], input_: str | None = None) -> str:
        joined = " ".join(args)
        if any(m in joined for m in ("-X", "--method")) or "mutation" in joined:
            self.planned.append(f"gh {joined}")
            return "{}"
        return super().run(args, input_)


def list_issues(gh: GhRunner, repo: str, state: str = "all") -> list[dict]:
    """Every issue (not PR) in the repo, paginated."""
    raw = gh.run(["api", f"repos/{repo}/issues?state={state}&per_page=100",
                  "--paginate"])
    # --paginate concatenates JSON arrays
    items: list[dict] = []
    dec = json.JSONDecoder()
    idx = 0
    raw = raw.strip()
    while idx < len(raw):
        chunk, end = dec.raw_decode(raw, idx)
        items.extend(chunk)
        idx = end
        while idx < len(raw) and raw[idx] in " \n\r\t":
            idx += 1
    return [i for i in items if "pull_request" not in i]


def ensure_label(gh: GhRunner, repo: str, name: str, color: str, desc: str) -> None:
    try:
        gh.run(["api", f"repos/{repo}/labels", "-X", "POST",
                "-f", f"name={name}", "-f", f"color={color}",
                "-f", f"description={desc}"])
    except GhError as exc:
        if "already_exists" not in str(exc) and "422" not in str(exc):
            raise


def create_issue(gh: GhRunner, repo: str, title: str, body: str,
                 labels: list[str]) -> dict:
    args = ["api", f"repos/{repo}/issues", "-X", "POST",
            "-f", f"title={title}", "-f", f"body={body}"]
    for lb in labels:
        args += ["-f", f"labels[]={lb}"]
    return json.loads(gh.run(args) or "{}")


def update_issue(gh: GhRunner, repo: str, number: int, **fields) -> None:
    args = ["api", f"repos/{repo}/issues/{number}", "-X", "PATCH"]
    for k, v in fields.items():
        args += ["-f", f"{k}={v}"]
    gh.run(args)


def comment(gh: GhRunner, repo: str, number: int, body: str) -> None:
    gh.run(["api", f"repos/{repo}/issues/{number}/comments", "-X", "POST",
            "-f", f"body={body}"])


def add_sub_issue(gh: GhRunner, parent_node: str, child_node: str) -> None:
    q = ("mutation($p: ID!, $c: ID!) { addSubIssue(input: {issueId: $p, "
         "subIssueId: $c}) { issue { id } } }")
    try:
        gh.graphql(q, p=parent_node, c=child_node)
    except GhError as exc:
        if "already" not in str(exc).lower():   # re-link is fine
            raise
