"""docassert command-line interface.

    docassert validate documents/charters/aurora.md
    docassert validate documents/**/*.md --junit out.xml --markdown comment.md

Exit code = number of BLOCKING (structural) failures, capped at 125 so large
counts can't wrap around the 8-bit exit-status space (256 failures must never
read as success). Advisory (AI) failures never affect the exit code, so CI is
gated only by deterministic checks.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import defaultdict
from pathlib import Path

from . import config, report, rtm
from .consistency import run_consistency
from .graph import build_graph
from .loader import load
from .models import CheckResult
from .semantic import run_semantic
from .structural import run_structural

# Default documents location; every document-reading command accepts
# --documents-dir to override it. Criteria / schema / consistency.yaml /
# profiles resolve via `config` (local override → packaged default).
DEFAULT_DOCUMENTS_DIR = "documents"

# POSIX exit statuses are 8-bit; 126+ carry shell meanings. Cap so a failure
# count can never wrap to 0.
_EXIT_CAP = 125


def _capped(failures: int) -> int:
    return min(failures, _EXIT_CAP)


def _build_id_index(documents_dir: Path) -> dict[str, list[str]]:
    """Map document id -> [paths] across the documents tree, for uniqueness checks."""
    index: dict[str, list[str]] = defaultdict(list)
    for path in documents_dir.rglob("*.md"):
        try:
            doc = load(path)
        except ValueError:
            continue
        if doc.id:
            index[doc.id].append(str(path))
    return index


def _validate_one(path: str, id_index: dict) -> list[CheckResult]:
    doc = load(path)
    kind = doc.kind or "charter"
    criteria = config.read_criteria(kind)
    schema = config.read_schema(kind)

    ctx = {
        "schema": schema,
        "required_sections": criteria.get("required_sections", []),
        "item_sections": criteria.get("item_sections", []),
        "steps_sections": criteria.get("steps_sections", []),
        "measurable_sections": criteria.get("measurable_sections", []),
        "id_index": id_index,
    }
    content = Path(path).read_text(encoding="utf-8")

    results: list[CheckResult] = []
    for spec in criteria.get("checks", []):
        if spec.get("type") == "structural":
            results.append(run_structural(doc, spec, ctx))
        elif spec.get("type") == "semantic":
            results.append(run_semantic(doc, spec, content))
    return results


def _expand(paths: list[str]) -> list[str]:
    files: list[str] = []
    for p in paths:
        matched = glob.glob(p, recursive=True)
        files.extend(matched if matched else [p])
    # de-dupe; keep only markdown docs that still exist (skip files a PR deleted)
    seen, out = set(), []
    for f in files:
        if f.endswith(".md") and f not in seen and os.path.isfile(f):
            seen.add(f)
            out.append(f)
    return out


def cmd_validate(args: argparse.Namespace) -> int:
    files = _expand(args.paths)
    if not files:
        print("docassert: no markdown documents matched.", file=sys.stderr)
        return 0

    id_index = _build_id_index(Path(args.documents_dir))
    results_by_doc: dict[str, list[CheckResult]] = {}
    for path in files:
        try:
            results_by_doc[path] = _validate_one(path, id_index)
        except FileNotFoundError as exc:
            print(f"docassert: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:  # malformed frontmatter → a real, blocking failure
            results_by_doc[path] = [CheckResult(
                "parse", False, True, str(exc), kind="structural")]

    print(report.console(results_by_doc))
    print("\n" + report.summary_line(results_by_doc))

    if args.junit:
        Path(args.junit).write_text(report.junit(results_by_doc))
    if args.markdown:
        Path(args.markdown).write_text(report.markdown(results_by_doc))
    if args.json:
        Path(args.json).write_text(report.json_report(results_by_doc))

    return _capped(sum(1 for rs in results_by_doc.values()
                       for r in rs if r.is_blocking_failure))


def cmd_consistency(args: argparse.Namespace) -> int:
    results = run_consistency(args.documents_dir, with_semantic=not args.no_semantic)
    results_by_doc = {"consistency (cross-document)": results}

    print(report.console(results_by_doc))
    print("\n" + report.summary_line(results_by_doc))

    if args.junit:
        Path(args.junit).write_text(report.junit(results_by_doc))
    if args.markdown:
        Path(args.markdown).write_text(
            report.markdown(results_by_doc, title="docassert consistency"))
    if args.json:
        Path(args.json).write_text(report.json_report(results_by_doc))

    return _capped(sum(1 for r in results if r.is_blocking_failure))


def _project_code(value: str | None) -> str | None:
    """Accept either a PRJ-NNN-CODE id or a bare CODE; return the CODE."""
    return value.split("-")[-1] if value else None


def cmd_rtm(args: argparse.Namespace) -> int:
    graph = build_graph(args.documents_dir)
    code = _project_code(args.project)
    text = rtm.render_csv(graph, code) if args.csv else rtm.render_markdown(graph, code)
    if args.out:
        Path(args.out).write_text(text)
        print(f"docassert: wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_projects(args: argparse.Namespace) -> int:
    from . import projects as proj
    plist = proj.load_projects(args.documents_dir)
    issues = proj.registry_issues(plist)
    for issue in issues:
        print(f"docassert: {issue}", file=sys.stderr)
    text = proj.render_yaml(plist)

    if args.check:
        current = Path(args.out or "projects.yaml")
        existing = current.read_text() if current.is_file() else ""
        if existing != text:
            print(f"docassert: {current} is stale — run `docassert projects --out {current}`",
                  file=sys.stderr)
            return 1
        print(f"docassert: {current} is up to date ({len(plist)} projects).")
        return 1 if issues else 0

    if args.out:
        Path(args.out).write_text(text)
        print(f"docassert: wrote {args.out} ({len(plist)} projects)")
    else:
        sys.stdout.write(text)
    return 1 if issues else 0


def cmd_status(args: argparse.Namespace) -> int:
    from . import status as status_mod
    if args.index:
        index = status_mod.build_index(args.documents_dir)
        if args.format == "json":
            text = status_mod.render_json(index)
        elif args.format == "html":
            text = status_mod.render_index_html(index)
        else:
            text = status_mod.render_index_markdown(index)
        tag = index["overall"]["rag"]
    else:
        model = status_mod.build_status(args.documents_dir, project=args.project)
        if args.project and not model["documents"]:
            print(f"docassert: no documents for project {args.project!r}", file=sys.stderr)
            return 2
        if args.format == "json":
            text = status_mod.render_json(model)
        elif args.format == "html":
            text = status_mod.render_html(model)
        else:
            text = status_mod.render_markdown(model, summary=args.summary)
        tag = model["rag"]
    if args.out:
        Path(args.out).write_text(text)
        print(f"docassert: wrote {args.out} (status: {tag})")
    else:
        sys.stdout.write(text)
    return 0


def cmd_pages(args: argparse.Namespace) -> int:
    """Build the whole Pages site: a portfolio index plus one page per project."""
    from . import projects as projects_mod
    from . import status as status_mod
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    docs_dir = args.documents_dir

    index = status_mod.build_index(docs_dir)
    (out / "index.html").write_text(status_mod.render_index_html(index))

    # shields.io endpoint badges: one for the portfolio, one per project
    # (https://img.shields.io/endpoint?url=<site>/badge.json)
    (out / "badge.json").write_text(
        status_mod.render_badge_json(index["overall"]["rag"]))
    (out / "badges").mkdir(exist_ok=True)

    execution = {}
    if getattr(args, "execution", None):
        import json as _json
        data = _json.loads(Path(args.execution).read_text())
        for proj in data.get("projects", []):
            execution[proj["id"]] = {**proj, "scope": data.get("scope"),
                                     "repo": proj.get("repo") or data.get("repo")}

    plist = projects_mod.load_projects(docs_dir)
    for p in plist:
        model = status_mod.build_status(docs_dir, project=p["id"])
        if p["id"] in execution:
            model["execution"] = execution[p["id"]]
        (out / f"{p['id']}.html").write_text(status_mod.render_html(model))
        (out / "badges" / f"{p['id']}.json").write_text(
            status_mod.render_badge_json(model["rag"], label=p["code"].lower()))

    (out / "RTM.md").write_text(rtm.render_markdown(build_graph(docs_dir)))
    print(f"docassert: wrote {out}/ — index + {len(plist)} project page(s) + badges + RTM.md "
          f"(portfolio: {index['overall']['rag']})")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Scaffold a repo with the default criteria, schema, profiles, templates,
    and consistency.yaml so a team can customize the standard."""
    created = config.init(args.dir)
    if created:
        print(f"docassert: scaffolded {', '.join(created)} in {args.dir}/")
    else:
        print(f"docassert: nothing to do — {args.dir}/ already has the config files")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract plain text from a source document (.docx/.pdf/.md/.txt) — the
    deterministic first step of doc-to-pmo conversion."""
    from . import extract as extract_mod
    try:
        text = extract_mod.extract(args.file)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"docassert: {exc}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"docassert: wrote {args.out} ({len(text)} chars)")
    else:
        sys.stdout.write(text)
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    """Scaffold a document of a kind from its template, with identity filled in."""
    from . import scaffold
    try:
        dest, notes = scaffold.new_document(
            args.kind, documents_dir=args.documents_dir, project=args.project,
            code=args.code, name=args.name, out=args.out)
    except (ValueError, FileExistsError) as exc:
        print(f"docassert: {exc}", file=sys.stderr)
        return 2
    print(f"docassert: created {dest}")
    for note in notes:
        print(f"docassert: {note}")
    return 0




def cmd_bridge(args: argparse.Namespace) -> int:
    """Execution bridge: scaffold/police/read the GitHub board from the docs.
    Scope flows documents -> GitHub only; the bridge never edits documents."""
    from .bridge import build_bridge_plan, ops
    from .bridge import gh as ghmod
    from .bridge.plan import filter_plan, plans_by_repo

    plan = build_bridge_plan(args.documents_dir)
    if getattr(args, "project", None):
        plan = filter_plan(plan, args.project)
    gh = ghmod.DryRunner() if getattr(args, "dry_run", False) else ghmod.GhRunner()

    # Repo resolution: an explicit --repo applies the whole plan to one
    # repository (single-repo portfolios, back-compatible); without it, each
    # project routes to the repo mapped on its anchor.
    if args.action != "create-board":
        if args.repo:
            repo_plans = {args.repo: plan}
        else:
            try:
                repo_plans = plans_by_repo(plan)
            except ValueError as exc:
                print(f"docassert bridge: {exc}", file=sys.stderr)
                return 2
            if not repo_plans and plan.skipped:
                for s in plan.skipped:
                    print(f"docassert bridge: skipped {s['id']}: {s['reason']}")
                return 0

    if args.action == "create-board":
        from .bridge import board as board_mod
        token = os.environ.get(args.board_token_env, "")
        if not token and not getattr(args, "dry_run", False):
            print(f"docassert bridge: no token in ${args.board_token_env}", file=sys.stderr)
            return 2
        bgh = gh if isinstance(gh, ghmod.DryRunner) else ghmod.GhRunner(token=token)
        proj = board_mod.create_project(bgh, args.title or "PMO board")
        print(f"docassert bridge: created project #{proj.get('number')} '{proj.get('title')}'")
        return 0

    board_cfg = None
    if args.project_number:
        token = os.environ.get(args.board_token_env, "")
        if not token and not getattr(args, "dry_run", False):
            print(f"docassert bridge: no token in ${args.board_token_env} "
                  "(needed for --project-number)", file=sys.stderr)
            return 2
        bgh = gh if isinstance(gh, ghmod.DryRunner) else ghmod.GhRunner(token=token)
        owner = args.project_owner or next(iter(repo_plans)).split("/")[0]
        board_cfg = {"gh": bgh, "owner": owner,
                     "number": args.project_number, "init": args.init_board}

    if args.action == "scaffold":
        for repo, sub in repo_plans.items():
            actions = ops.scaffold(sub, gh, repo, docs_url=args.docs_url,
                                   board_cfg=board_cfg)
            for a in actions:
                print(f"docassert bridge: [{repo}] {a}")
        if isinstance(gh, ghmod.DryRunner):
            print(f"docassert bridge: dry run — {len(gh.planned)} mutation(s) planned")
            for m in gh.planned:
                print(f"  {m}")
        return 0
    if args.action == "reconcile":
        worst = 0
        for repo, sub in repo_plans.items():
            lines, code = ops.reconcile(sub, gh, repo)
            for line in lines:
                print(f"docassert bridge: [{repo}] {line}")
            worst = max(worst, code)
        return worst
    if args.action == "status":
        merged: dict = {"repo": None, "projects": [], "scope": {"unverified": [], "orphaned": []}}
        for repo, sub in repo_plans.items():
            data = ops.status(sub, gh, repo)
            for proj in data.get("projects", []):
                proj["repo"] = repo
                merged["projects"].append(proj)
            for key in ("unverified", "orphaned"):
                for item in data.get("scope", {}).get(key, []):
                    item["repo"] = repo
                    merged["scope"][key].append(item)
        if len(repo_plans) == 1:
            merged["repo"] = next(iter(repo_plans))
        sys.stdout.write(ops.to_json(merged) if args.json else
                         ops.render_status(merged) + "\n")
        if args.json and args.out:
            Path(args.out).write_text(ops.to_json(merged))
        return 0
    print(f"docassert bridge: unknown action {args.action!r}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    from . import __version__
    parser = argparse.ArgumentParser(prog="docassert",
                                     description="Unit testing for business documents.")
    parser.add_argument("--version", action="version", version=f"docassert {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def docs_dir_opt(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--documents-dir", default=DEFAULT_DOCUMENTS_DIR,
                        help=f"Documents tree to read (default: {DEFAULT_DOCUMENTS_DIR}/).")

    def report_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--junit", help="Write a JUnit XML report to this path.")
        sp.add_argument("--markdown", help="Write a PR-comment markdown report to this path.")
        sp.add_argument("--json", help="Write a machine-readable JSON report to this path.")

    v = sub.add_parser("validate", help="Validate documents against their criteria.")
    v.add_argument("paths", nargs="+", help="Markdown files or globs.")
    report_opts(v)
    docs_dir_opt(v)
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("consistency", help="Check cross-document traceability.")
    report_opts(c)
    c.add_argument("--no-semantic", action="store_true",
                   help="Skip AI alignment (structural consistency only).")
    docs_dir_opt(c)
    c.set_defaults(func=cmd_consistency)

    r = sub.add_parser("rtm", help="Generate the requirements traceability matrix.")
    r.add_argument("--out", help="Write to this path instead of stdout.")
    r.add_argument("--csv", action="store_true", help="Emit CSV instead of Markdown.")
    r.add_argument("--project", help="Scope to one project (PRJ-NNN-CODE id or CODE).")
    docs_dir_opt(r)
    r.set_defaults(func=cmd_rtm)

    s = sub.add_parser("status", help="Derive a project status page from the documents.")
    s.add_argument("--format", choices=["md", "json", "html"], default="md",
                   help="Output format (default: md).")
    s.add_argument("--summary", action="store_true",
                   help="Condensed markdown (RAG + signals, no inventory table).")
    s.add_argument("--project", help="Scope the status to one project (its PRJ-NNN-CODE id).")
    s.add_argument("--index", action="store_true",
                   help="Render the multi-project portfolio index instead of one status.")
    s.add_argument("--out", help="Write to this path instead of stdout.")
    docs_dir_opt(s)
    s.set_defaults(func=cmd_status)

    pg = sub.add_parser("pages", help="Build the full Pages site (portfolio index + a page per project).")
    pg.add_argument("--out", default="_site", help="Output directory (default: _site).")
    pg.add_argument("--execution", help="Optional bridge-status JSON; adds Delivery and Scope panels to project pages.")
    docs_dir_opt(pg)
    pg.set_defaults(func=cmd_pages)

    p = sub.add_parser("projects", help="Generate the project registry from the project.md anchors.")
    p.add_argument("--out", help="Write to this path instead of stdout (e.g. projects.yaml).")
    p.add_argument("--check", action="store_true",
                   help="Exit non-zero if the registry file is stale (CI freshness gate).")
    docs_dir_opt(p)
    p.set_defaults(func=cmd_projects)

    ini = sub.add_parser("init", help="Scaffold the default criteria/schema/profiles/templates into a repo.")
    ini.add_argument("dir", nargs="?", default=".", help="Target directory (default: current).")
    ini.set_defaults(func=cmd_init)

    ex = sub.add_parser("extract", help="Extract plain text from a source doc (.docx/.pdf/.md/.txt) for conversion.")
    ex.add_argument("file", help="Source document (.docx / .pdf / .md / .txt).")
    ex.add_argument("--out", help="Write to this path instead of stdout.")
    ex.set_defaults(func=cmd_extract)

    n = sub.add_parser("new", help="Scaffold a document of a kind from its template, identity filled in.")
    n.add_argument("kind", help="Document kind (e.g. charter, brd, project).")
    n.add_argument("--project", help="Owning project id, PRJ-NNN-CODE (for `new project`: the id to create).")
    n.add_argument("--code", help="For `new project`: 2–6 letter code; the sequence number is auto-picked.")
    n.add_argument("--name", help="For `new project`: the project name.")
    n.add_argument("--out", help="Write to this path instead of the default location.")
    docs_dir_opt(n)
    n.set_defaults(func=cmd_new)


    b = sub.add_parser("bridge", help="Execution bridge: scaffold and police the GitHub board from approved stories.")
    b.add_argument("action", choices=["scaffold", "reconcile", "status", "create-board"],
                   help="scaffold: docs -> issues/board · reconcile: police the board · status: delivery figures.")
    b.add_argument("--repo", help="Target GitHub repo (OWNER/NAME) for the whole plan; "
                   "omit to route each project to the `repo:` on its anchor.")
    b.add_argument("--project", help="Scope to one project (PRJ-NNN-CODE id or CODE).")
    b.add_argument("--docs-url", help="Base URL of the documents repo, for source links in issue bodies.")
    b.add_argument("--dry-run", action="store_true", help="Print planned mutations without executing them.")
    b.add_argument("--json", action="store_true", help="status: emit JSON.")
    b.add_argument("--out", help="status --json: also write to this path.")
    b.add_argument("--title", help="create-board: the new project's title.")
    b.add_argument("--project-owner", help="Board owner login (default: the repo owner).")
    b.add_argument("--project-number", type=int, help="Projects v2 board number to sync items onto.")
    b.add_argument("--init-board", action="store_true", help="Ensure the Type/Doc/PMO Project fields exist.")
    b.add_argument("--board-token-env", default="PROJECTS_TOKEN",
                   help="Env var holding the project-scoped token (default: PROJECTS_TOKEN).")
    docs_dir_opt(b)
    b.set_defaults(func=cmd_bridge)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
