# docassert

[![PyPI](https://img.shields.io/pypi/v/docassert)](https://pypi.org/project/docassert/)
[![Python](https://img.shields.io/pypi/pyversions/docassert)](https://pypi.org/project/docassert/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

![docassert demo — a weak charter is blocked, fixed, and cleared](https://raw.githubusercontent.com/c4g-john/docassert/main/docs/demo.svg)

**Unit testing for business documents.** Validate structured Markdown documents
(charters, BRDs, PRDs, risk registers, …) against a configurable audit standard:
deterministic structural checks that gate a merge, plus optional AI-graded
semantic checks that advise. Requirements trace end to end, and project status is
derived from the documents rather than self-reported.

docassert is the reference implementation of **[PMO as Code](https://c4g-john.github.io/pmo-as-code/)** —
a vendor-neutral standard for running a PMO from version-controlled, declarative
files. It implements the [PMO as Code specification](https://github.com/c4g-john/pmo-as-code-spec) **v0.3** and passes its [conformance suite](https://github.com/c4g-john/pmo-as-code-spec/tree/main/conformance) in CI.

## Install

```bash
pipx install docassert          # recommended — installs the CLI in its own isolated env
# or:
pip install docassert
# with the AI advisory extra:
pip install "docassert[ai]"
```

## Quickstart

```bash
docassert new project --code AUR --name "Aurora"   # anchor a project (auto-numbered id)
docassert new charter --project PRJ-001-AUR        # scaffold a charter into it
docassert validate documents/**/*.md  # unit-test your documents
docassert consistency                 # cross-document traceability + profile completeness
docassert status --index              # derived RAG per project
docassert pages --out _site           # a portfolio dashboard + a page per project
```

Config resolves **local override → packaged default**: docassert ships sensible
defaults, and your repo's own `criteria/` (or `schema/`, `profiles/`,
`consistency.yaml`) wins when present. `docassert init` copies the defaults in so
you can customize them — including the **doc-to-pmo Claude skill** into
`.claude/skills/`, so Claude Code in your repo knows how to convert existing
Word/PDF documents into testable docassert documents (faithfully — gaps are
flagged as TODOs, never invented). The skill's source is
[`skills/doc-to-pmo/SKILL.md`](skills/doc-to-pmo/SKILL.md).

## Commands

| Command | What it does |
|---|---|
| `docassert validate <globs>` | Validate documents against their kind's criteria. Exit code = number of blocking failures (capped at 125). Reports: `--junit` / `--markdown` / `--json`. |
| `docassert consistency` | Cross-document checks: referential integrity, coverage, required links, profile completeness. Reports: `--junit` / `--markdown` / `--json`. |
| `docassert rtm [--project ID]` | Requirements traceability matrix (Markdown or CSV). |
| `docassert status [--project ID] [--index]` | Derived project status (md / json / html). |
| `docassert pages --out DIR` | Build the portfolio site (index + a page per project + shields.io badge endpoints `badge.json` / `badges/<ID>.json`). |
| `docassert projects [--out] [--check]` | Generate / verify the project registry. |
| `docassert new <kind> --project ID` | Scaffold a document from its template with identity filled in (`new project --code XYZ` auto-numbers the id); suggests the next free item ids. |
| `docassert init [DIR]` | Scaffold the default config into a repo. |
| `docassert bridge <action> --repo O/N` | Execution bridge: `scaffold` Features/Stories from approved user stories, `reconcile` (police the board against the docs), `status` (delivery figures). Needs the GitHub CLI. |
| `docassert extract <file>` | Extract plain text from a source `.docx` / `.pdf` / `.md` / `.txt` (the first step of doc-to-pmo conversion). Needs the `convert` extra: `pip install "docassert[convert]"`. |

Every document-reading command accepts `--documents-dir` (default `documents/`).
The full flag-by-flag reference, and what 1.x does and does not promise to
keep stable, live in [STABILITY.md](STABILITY.md).
AI alignment grades at most `alignment_limit` links per run (default 25; set it
in `consistency.yaml`, `0` = no cap) so API cost stays bounded on large graphs.

## Document kinds

Twenty kinds, each a `templates/<kind>.template.md` + `schema/<kind>.schema.json`
+ `criteria/<kind>.criteria.yaml` trio: `project`, `charter`, `business-case`,
`brd`, `prd`, `frnfr`, `user-story`, `test-cases`, `adr`, `risk-register`,
`raci-stakeholder`, `qa-test-plan`, `data-migration-plan`,
`release-cutover-plan`, `rollback-plan`, `hypercare-plan`, `runbook`,
`status-report`, `post-implementation-review`, `benefits-realization`. Adding a
kind is adding a trio — no code for the common cases.

## Two tiers of checks

- **Structural — deterministic, blocking.** Required fields and sections,
  measurable success criteria, risks with owner + mitigation, resolving
  references, unique ids. Plain Python, reliable enough to gate a merge.
  Within this tier, *integrity* checks (malformed items, bad types, duplicate
  ids) block at any status, while *completeness* checks relax to advisory on
  `status: draft` and gate once a document is proposed — WIP is never punished.
- **Semantic — AI-graded, advisory.** Scored via the Anthropic API and posted to
  the PR — never blocking. Set `ANTHROPIC_API_KEY` to enable; skipped otherwise.

## Privacy

Structural checks run **entirely locally** — no document content leaves your
machine or CI runner. Semantic checks are the one exception: when
`ANTHROPIC_API_KEY` is set, the graded excerpts (section text, linked item
text) are sent to the **Anthropic API** for scoring. Without the key, semantic
checks are skipped and nothing is sent anywhere. Alignment grading is capped at
`alignment_limit` links per run (default 25). If your documents are
confidential, run without the key or review [Anthropic's data-usage
policies](https://www.anthropic.com/legal/commercial-terms) first.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

This repo ships example `documents/` (four sample projects) that the test suite
validates against.

## The reference deployment

[**pmo-as-code-pipeline**](https://github.com/c4g-john/pmo-as-code-pipeline) is a
living example — sample projects, the gate on every pull request, and a published
dashboard at
[c4g-john.github.io/pmo-as-code-pipeline](https://c4g-john.github.io/pmo-as-code-pipeline/).
The standard's site is [c4g-john.github.io/pmo-as-code](https://c4g-john.github.io/pmo-as-code/).

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). © 2026 C4G Enterprises Inc.
