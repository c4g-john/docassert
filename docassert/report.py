"""Render check results as console text, PR-comment markdown, or JUnit XML."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from .models import CheckResult

_TICK = "✓"
_CROSS = "✗"
_DASH = "—"


def _mark(r: CheckResult) -> str:
    if r.kind == "semantic" and r.score is None:
        return "○"  # ○ skipped/unavailable
    return _TICK if r.passed else _CROSS


def console(results_by_doc: dict[str, list[CheckResult]]) -> str:
    lines: list[str] = []
    for path, results in results_by_doc.items():
        lines.append(f"\n{path}")
        for r in results:
            tier = "structural" if r.kind == "structural" else "advisory  "
            gate = "BLOCK" if r.is_blocking_failure else "     "
            score = f" [{r.score:.2f}]" if r.score is not None else ""
            lines.append(f"  {_mark(r)} {gate} {tier} {r.check_id}{score}: {r.detail}")
    return "\n".join(lines)


def summary_line(results_by_doc: dict[str, list[CheckResult]]) -> str:
    blocking = sum(1 for rs in results_by_doc.values() for r in rs if r.is_blocking_failure)
    docs = len(results_by_doc)
    if blocking:
        return f"{_CROSS} {blocking} blocking failure(s) across {docs} document(s) {_DASH} merge blocked."
    return f"{_TICK} All structural checks passed across {docs} document(s) {_DASH} clear to merge."


def markdown(results_by_doc: dict[str, list[CheckResult]],
             title: str = "docassert audit") -> str:
    """PR-comment body."""
    out = [f"## {title}", "", summary_line(results_by_doc), ""]
    for path, results in results_by_doc.items():
        out.append(f"### `{path}`")
        out.append("")
        out.append("| | Check | Tier | Result |")
        out.append("|---|---|---|---|")
        for r in results:
            tier = "structural (blocking)" if r.kind == "structural" else "AI advisory"
            score = f" · score {r.score:.2f}" if r.score is not None else ""
            if r.kind == "semantic" and r.score is None:
                emoji = "⚪"  # advisory check skipped/unavailable
            elif r.passed:
                emoji = "🟢"
            else:
                emoji = "🔴"
            out.append(f"| {emoji} | `{r.check_id}` | {tier} | {r.detail}{score} |")
        out.append("")
    out.append("<sub>Structural checks block the merge. AI advisory checks inform "
               "reviewers but never block. Configure criteria in `criteria/`.</sub>")
    return "\n".join(out)


def junit(results_by_doc: dict[str, list[CheckResult]]) -> str:
    total = sum(len(rs) for rs in results_by_doc.values())
    failures = sum(1 for rs in results_by_doc.values()
                   for r in rs if r.is_blocking_failure)
    suites = ET.Element("testsuites", tests=str(total), failures=str(failures))
    for path, results in results_by_doc.items():
        suite = ET.SubElement(suites, "testsuite", name=path,
                              tests=str(len(results)),
                              failures=str(sum(1 for r in results if r.is_blocking_failure)))
        for r in results:
            case = ET.SubElement(suite, "testcase",
                                 classname=f"{path}:{r.kind}", name=r.check_id)
            if r.is_blocking_failure:
                ET.SubElement(case, "failure", message=r.detail).text = r.detail
            elif r.kind == "semantic" and not r.passed:
                # advisory failures surface as skipped, never as build failures
                ET.SubElement(case, "skipped", message=r.detail)
    xml = ET.tostring(suites, encoding="unicode")
    return minidom.parseString(xml).toprettyxml(indent="  ")
