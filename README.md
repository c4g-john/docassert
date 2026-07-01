# docassert

[![PyPI](https://img.shields.io/pypi/v/docassert)](https://pypi.org/project/docassert/)
[![Python](https://img.shields.io/pypi/pyversions/docassert)](https://pypi.org/project/docassert/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**Unit testing for business documents.** Validate structured Markdown documents
(charters, BRDs, PRDs, risk registers, …) against a configurable audit standard:
deterministic structural checks that gate a merge, plus optional AI-graded
semantic checks that advise. Requirements trace end to end, and project status is
derived from the documents rather than self-reported.

docassert is the reference implementation of **[PMO as Code](https://c4g-john.github.io/pmo-as-code/)** —
a vendor-neutral standard for running a PMO from version-controlled, declarative files.

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
docassert init                        # scaffold criteria/schema/profiles/templates into your repo
docassert validate documents/**/*.md  # unit-test your documents
docassert consistency                 # cross-document traceability + profile completeness
docassert status --index              # derived RAG per project
docassert pages --out _site           # a portfolio dashboard + a page per project
```

Config resolves **local override → packaged default**: docassert ships sensible
defaults, and your repo's own `criteria/` (or `schema/`, `profiles/`,
`consistency.yaml`) wins when present. `docassert init` copies the defaults in so
you can customize them.

## Commands

| Command | What it does |
|---|---|
| `docassert validate <globs>` | Validate documents against their kind's criteria. Exit code = number of blocking failures. |
| `docassert consistency` | Cross-document checks: referential integrity, coverage, required links, profile completeness. |
| `docassert rtm [--project ID]` | Requirements traceability matrix (Markdown or CSV). |
| `docassert status [--project ID] [--index]` | Derived project status (md / json / html). |
| `docassert pages --out DIR` | Build the portfolio site (index + a page per project). |
| `docassert projects [--out] [--check]` | Generate / verify the project registry. |
| `docassert init [DIR]` | Scaffold the default config into a repo. |

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
- **Semantic — AI-graded, advisory.** Scored via the Anthropic API and posted to
  the PR — never blocking. Set `ANTHROPIC_API_KEY` to enable; skipped otherwise.

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
