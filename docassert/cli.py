"""docassert command-line interface.

    docassert validate documents/charters/aurora.md
    docassert validate documents/**/*.md --junit out.xml --markdown comment.md

Exit code = number of BLOCKING (structural) failures. Advisory (AI) failures
never affect the exit code, so CI is gated only by deterministic checks.
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

# The user's documents live here; criteria / schema / consistency.yaml / profiles
# resolve via `config` (local override → packaged default).
DOCUMENTS_DIR = Path("documents")


def _build_id_index() -> dict[str, list[str]]:
    """Map document id -> [paths] across all documents/, for uniqueness checks."""
    index: dict[str, list[str]] = defaultdict(list)
    for path in DOCUMENTS_DIR.rglob("*.md"):
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

    id_index = _build_id_index()
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

    return sum(1 for rs in results_by_doc.values()
               for r in rs if r.is_blocking_failure)


def cmd_consistency(args: argparse.Namespace) -> int:
    results = run_consistency(DOCUMENTS_DIR, with_semantic=not args.no_semantic)
    results_by_doc = {"consistency (cross-document)": results}

    print(report.console(results_by_doc))
    print("\n" + report.summary_line(results_by_doc))

    if args.junit:
        Path(args.junit).write_text(report.junit(results_by_doc))
    if args.markdown:
        Path(args.markdown).write_text(
            report.markdown(results_by_doc, title="docassert consistency"))

    return sum(1 for r in results if r.is_blocking_failure)


def _project_code(value: str | None) -> str | None:
    """Accept either a PRJ-NNN-CODE id or a bare CODE; return the CODE."""
    return value.split("-")[-1] if value else None


def cmd_rtm(args: argparse.Namespace) -> int:
    graph = build_graph(DOCUMENTS_DIR)
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
    plist = proj.load_projects(DOCUMENTS_DIR)
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
        index = status_mod.build_index(DOCUMENTS_DIR)
        if args.format == "json":
            text = status_mod.render_json(index)
        elif args.format == "html":
            text = status_mod.render_index_html(index)
        else:
            text = status_mod.render_index_markdown(index)
        tag = index["overall"]["rag"]
    else:
        model = status_mod.build_status(DOCUMENTS_DIR, project=args.project)
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

    index = status_mod.build_index(DOCUMENTS_DIR)
    (out / "index.html").write_text(status_mod.render_index_html(index))

    plist = projects_mod.load_projects(DOCUMENTS_DIR)
    for p in plist:
        model = status_mod.build_status(DOCUMENTS_DIR, project=p["id"])
        (out / f"{p['id']}.html").write_text(status_mod.render_html(model))

    (out / "RTM.md").write_text(rtm.render_markdown(build_graph(DOCUMENTS_DIR)))
    print(f"docassert: wrote {out}/ — index + {len(plist)} project page(s) + RTM.md "
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


def main(argv: list[str] | None = None) -> int:
    from . import __version__
    parser = argparse.ArgumentParser(prog="docassert",
                                     description="Unit testing for business documents.")
    parser.add_argument("--version", action="version", version=f"docassert {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate documents against their criteria.")
    v.add_argument("paths", nargs="+", help="Markdown files or globs.")
    v.add_argument("--junit", help="Write a JUnit XML report to this path.")
    v.add_argument("--markdown", help="Write a PR-comment markdown report to this path.")
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("consistency", help="Check cross-document traceability.")
    c.add_argument("--junit", help="Write a JUnit XML report to this path.")
    c.add_argument("--markdown", help="Write a PR-comment markdown report to this path.")
    c.add_argument("--no-semantic", action="store_true",
                   help="Skip AI alignment (structural consistency only).")
    c.set_defaults(func=cmd_consistency)

    r = sub.add_parser("rtm", help="Generate the requirements traceability matrix.")
    r.add_argument("--out", help="Write to this path instead of stdout.")
    r.add_argument("--csv", action="store_true", help="Emit CSV instead of Markdown.")
    r.add_argument("--project", help="Scope to one project (PRJ-NNN-CODE id or CODE).")
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
    s.set_defaults(func=cmd_status)

    pg = sub.add_parser("pages", help="Build the full Pages site (portfolio index + a page per project).")
    pg.add_argument("--out", default="_site", help="Output directory (default: _site).")
    pg.set_defaults(func=cmd_pages)

    p = sub.add_parser("projects", help="Generate the project registry from the project.md anchors.")
    p.add_argument("--out", help="Write to this path instead of stdout (e.g. projects.yaml).")
    p.add_argument("--check", action="store_true",
                   help="Exit non-zero if the registry file is stale (CI freshness gate).")
    p.set_defaults(func=cmd_projects)

    ini = sub.add_parser("init", help="Scaffold the default criteria/schema/profiles/templates into a repo.")
    ini.add_argument("dir", nargs="?", default=".", help="Target directory (default: current).")
    ini.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
