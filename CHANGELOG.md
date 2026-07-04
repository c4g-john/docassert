# Changelog

All notable changes to docassert. Format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [SemVer](https://semver.org/).

## [1.0.0] — 2026-07-04

The stability release. Functionally identical to 0.20.2 — the number is the
promise: the guarantees in [STABILITY.md](STABILITY.md) (CLI surface,
machine-readable output shapes, exit-code semantics, packaged-data semantics,
and the spec-first relationship) are now in force. Implements PMO as Code
spec v0.8.0; the 73-case conformance suite runs in CI at that tag.

### Changed
- Version 1.0.0; classifier Development Status :: 5 — Production/Stable.
- No functional changes from 0.20.2.

## [0.20.2] — 2026-07-04

Defect-fix release from a full code/content/automation audit. No CLI surface
changes.

### Fixed
- **Bridge: a converged (closed) duplicate issue could shadow the real open
  issue.** The GitHub API lists issues newest-first while the marker index
  assumed oldest-first, so `bridge status` reported features and stories as
  done when their real issues were open, `bridge scaffold` updated the wrong
  issue, and `bridge reconcile` refreshed a closed scope report. The index now
  ranks open before closed, then lowest number.
- `status --format html` crashed on an operations `review_by` that was
  malformed but 10 characters long (e.g. `2026-13-45`); all renderer date
  math now tolerates what derive tolerates.
- The verdict tooltip could read "No amber or red causes recorded." on an
  amber page: an amber/red latest status report and profile completeness gaps
  (required kinds missing or incomplete, recommended kinds open, unknown
  profile) were derived into the RAG but missing from the cause list. The
  verdict sentence and the HEALTH stat tooltip now state every cause
  `derive_rag` uses.
- The green verdict claimed "every document passes audit" even when a draft
  document was failing checks; it now says "every approved document passes
  audit" and names failing drafts as work in progress.
- The amber verdict counted every open risk while the tooltip counted only
  risks at or above the appetite; both now respect the appetite threshold.
- Inline dashboard JSON over-escaped `</` (rendering a stray backslash in any
  text containing it); the payload now round-trips losslessly.
- `validate` silently validated documents with no `kind` as charters; a
  missing kind is now a blocking failure that says so.
- Project pages showed scope findings (unverified/orphaned issues) from other
  projects' repositories; the scope panel is now filtered to the repo the
  project routes to.
- `bridge --project-number` without `--project-owner` crashed when no project
  routed to a repository; it now exits with a clear message.
- `plans_by_repo` shared one skipped list across sub-plans.
- Projects v2 board lookups only resolved user owners; organization-owned
  boards now work (user first, then organization).
- `sequence-acyclic` is now an iterative DFS, so a dependency chain as long
  as the item count cannot hit the recursion limit.

### Changed
- Criteria/schema/consistency reads are cached on (path, mtime); index and
  pages builds load the document corpus once instead of once per project.
- CI tests Python 3.14; classifiers updated.

## [0.20.1] — 2026-07-05

### Added
- Tooltips across the status pages (native `title` attributes; still fully
  self-contained): derivation rules on every stat, gap lists on coverage
  meters, full text and scope-point breakdowns on sequence bars, risk
  descriptions on matrix chips, the temporal-fact rule on milestones, the
  raw cause list on the verdict, and audit/state explanations on tables.

## [0.20.0] — 2026-07-05

### Changed
- Work charts drop the time axis (spec 0.8.0): features chart by dependency
  sequence (`after` layers for position) and scope size (width ∝ scope
  points = traced stories + verifying acceptance criteria — document
  arithmetic, no estimation; XS/S/M/L/XL over published buckets). The chart
  derives from documents alone, so un-bridged projects get it too; execution
  facts color the states (done/open/blocked/scoped).

### Added
- The `after` sequencing relation (PR→PR) with the always-blocking
  `sequence-acyclic` consistency check. Conformance ref: v0.8.0.

## [0.19.0] — 2026-07-05

### Changed
- Risk appetite (spec 0.7.0): open risks amber the derived status only at or
  above `risk_amber_score` (probability × impact, default 6; `0` restores the
  strict behavior). The old any-open-risk rule punished risk documentation
  and rewarded empty registers. Below-threshold exposure stays fully
  reported on every surface.

### Added
- An approved charter's `dates.target` renders as an implicit "Charter
  target" milestone, so every chartered project has a timeline anchor.

## [0.18.0] — 2026-07-04

### Changed
- Status pages redesigned as decision-grade dashboards (from the sponsor's
  design handoff): a verdict composed deterministically from the actual
  status causes, a six-stat cluster, coverage meters with the document-set
  checklist, a milestone timeline (temporal facts only — a past date renders
  as elapsed, never as done), execution lanes spanning real issue lifetimes,
  an interactive risk heat matrix with an expandable register, filterable
  document/work views, and recent document activity from git history. Pages
  remain fully self-contained (no external requests); the portfolio index
  server-renders its rows so it degrades without JavaScript.

### Added
- Dated charter milestones parsed per spec 0.6.0 (`- <label>: YYYY-MM-DD`,
  colon or dash separators) with the advisory `milestones-dated` check; the
  index gains per-project coverage percentage and next dated marker; bridge
  status carries per-issue facts (title, state, dates, assignee, labels, url)
  for presentation only — execution never alters the derived RAG.

## [0.17.0] — 2026-07-04

### Added
- `STABILITY.md`: the 1.x stability and deprecation policy — what the CLI
  surface, machine-readable outputs, exit codes, and packaged data guarantee,
  and how deprecations are announced — with a CLI reference generated from
  the live argument parser.

### Changed
- Coverage floor raised from 80% to 85% (current: 85.3%).

## [0.16.0] — 2026-07-04

### Added
- The `operations` document kind (spec 0.5.0): a governed service catalog
  with `Level`/`Measure` fields on `SVC` items, a required `review_by` date,
  the `svc-items-complete` (once-proposed) and `ops-review-fresh` (advisory)
  checks, an `operations` profile, and review staleness as an amber input to
  derived status — BAU without invented end dates. Conformance ref: v0.5.0.

## [0.15.0] — 2026-07-04

### Added
- Risk disposition (spec 0.4.0): `RISK` items may carry
  `Status: open | mitigated | accepted | closed` (absent means open). Only
  open risks drive the derived RAG and the open-risk signals, so a governed
  register earns green through recorded dispositions instead of deletion.
  Invalid dispositions fail the new always-blocking `risk-disposition-valid`
  check. The status-page risk table shows each risk's disposition, and the
  portfolio index counts open risks only. Conformance suite ref: v0.4.0.

## [0.14.1] — 2026-07-04

### Fixed
- Bridge concurrency safety (both found live on the PMO as Code portfolio's
  launch day): scaffolding now converges on one open issue per marker,
  closing racing duplicates in favor of the lowest number, and board field
  initialization treats an already-existing field as success.

## [0.14.0] — 2026-07-03

### Added
- Bridge commands accept `--project` (PRJ-NNN-CODE id or bare code) to scope
  the plan to one project.
- Project anchors accept an optional `repo: OWNER/NAME` field (spec 0.3.2).
  Without `--repo`, bridge commands route each project to its mapped
  repository; projects sharing a repository reconcile as a union, and
  `--repo` still applies the whole plan to one repository unchanged.
- Bridge status output carries per-project and per-scope-item `repo`, and
  status pages link issues through it, so multi-repository portfolios render
  correctly.

## [0.13.0] — 2026-07-03

### Added
- Project status pages render open risks as a table: ID, description, the
  business requirements threatened, probability and impact (color-coded),
  owner, and the full response text. The status model carries `description`,
  `threatens`, and `response` per risk alongside the existing ratings.

## [0.12.1] — 2026-07-03

### Changed
- Default rubrics: user-story traces are graded as slices — a story may
  implement part of its requirement with sibling stories covering the rest,
  which is exactly how the execution bridge decomposes features.

## [0.12.0] — 2026-07-03

### Added
- Alignment rules accept optional `child_type` / `parent_type` filters, and
  rules match in order with the first match grading a link — so different
  relations can carry different rubrics.

### Changed
- Default rubrics are now calibrated per relation: PR→BR traces are judged as
  contribution to a business outcome (a mechanism need not restate the KPI),
  and `verifies` criteria are judged as testable slices (several criteria may
  share one requirement without penalty). Reworded prompts change cache keys,
  so affected links re-grade on the next keyed run.

## [0.11.0] — 2026-07-03

### Changed
- `alignment_limit` now budgets API calls instead of links: grades already in
  the semantic cache replay for free, so runs that persist `.docassert-cache`
  (for example with `actions/cache`) walk the whole graph a budget at a time
  instead of re-grading the same first links forever.
- Advisory grading responses get more room (`max_tokens` 400 → 800), and a
  response truncated mid-rationale is recovered instead of discarded — the
  score and pass fields arrive before the rationale, so the grade survives
  with a `[truncated]` marker.
- `DOCASSERT_MODEL` / `DOCASSERT_CACHE` are now the preferred environment
  variables; the legacy `DOCUNIT_*` names still work.

## [0.10.1] — 2026-07-03

### Fixed
- Bridge issue bodies now link Source paths relative to the docs repository
  root, so the links stay valid when CI checks the documents out into a
  subdirectory (previously the checkout prefix leaked into the URL and the
  link 404ed).

## [0.10.0] — 2026-07-03

### Added
- `bridge status --json` now includes read-only scope classification
  (`scope.unverified` / `scope.orphaned`) alongside delivery figures.
- `docassert pages --execution report.json` renders Delivery (stories closed
  per feature, with progress bars) and Scope panels on project status pages,
  next to the document-derived signals. Documents stay the scope authority;
  the board supplies only execution state.

## [0.9.0] — 2026-07-03

### Added
- Projects v2 board support in the bridge: `bridge create-board --title`, and
  `bridge scaffold --project-number N [--init-board]` mirrors every managed
  issue onto the board with Type (Feature/Story), Doc, and PMO Project fields.
  Board calls use a separate project-scoped token (`--board-token-env`,
  default PROJECTS_TOKEN), so the issues layer keeps the least-privilege
  default credential.

## [0.8.1] — 2026-07-02

### Fixed
- `bridge scaffold` re-runs no longer fail when sub-issue links already exist
  (GitHub reports the duplicate in wording the tolerance check missed).

## [0.8.0] — 2026-07-02

### Added
- **The execution bridge** (`docassert bridge scaffold|reconcile|status`):
  scaffolds GitHub Features (product requirements) and Stories (approved user
  stories) as parent/sub-issues, polices the board against the documents
  (`scope:unverified` / `scope:orphaned` labels, one pinned scope report,
  non-zero exit on drift), and reads delivery progress. Requires the GitHub
  CLI; `--dry-run` prints planned mutations. Scope flows documents → GitHub
  only; the bridge never edits documents.

## [Unreleased]

### Added
- CI runs the PMO as Code conformance suite (spec v0.3.0, 64 cases) on every
  change; the README claims spec v0.3.

## [0.7.1] — 2026-07-02

### Changed
- Internal: split the 546-line `status.py` into a `docassert.status` package
  (`derive` model + `render` views) and de-duplicated the HTML escaper. Public
  API unchanged.

### Fixed
- Packaging now auto-discovers subpackages (`packages.find`), so nested
  packages like `docassert.status` ship in the wheel. The previous explicit
  `packages = ["docassert"]` would have omitted them.

## [0.7.0] — 2026-07-02

### Changed
- **Drafts are never punished for incompleteness.** Per-document checks now
  carry a severity: integrity checks (malformed items, type/format errors,
  duplicate ids) block at any status, while completeness checks (missing
  required fields, empty sections, ownerless risks, unmeasurable criteria) are
  **advisory while `status: draft`** and block once a document is proposed or
  beyond (`blocking: once-proposed` in criteria). Found by dogfooding a real
  BRD whose draft charter legitimately has no budget yet.
- Frontmatter validation split accordingly: `frontmatter-schema` (wellformed
  types/formats, always blocks) + new `frontmatter-complete` (required fields
  present, once-proposed). `dates-consistent` treats absent dates as
  completeness and only hard-fails invalid or inverted dates.

### Fixed
- `unique-id` no longer false-positives when the same file is referenced by
  different path spellings (absolute vs relative): paths are resolved before
  comparison.

## [0.6.0] — 2026-07-02

### Added
- **Status badges**: `docassert pages` now emits shields.io endpoint payloads —
  `badge.json` (portfolio) and `badges/<PROJECT-ID>.json` (per project) — so a
  README can carry a live derived-status badge:
  `https://img.shields.io/endpoint?url=<site>/badge.json`.
- Developer-trust infrastructure: mypy in CI (clean), a coverage floor (80%),
  a Windows CI leg, `CONTRIBUTING.md`, and issue templates.

## [0.5.0] — 2026-07-02

### Added
- `--json PATH` on `validate` and `consistency` — a machine-readable report
  (per-check results + a summary block) alongside `--junit` / `--markdown`.
- `CHANGELOG.md` (this file) and a **Privacy** section in the README: structural
  checks are fully local; semantic checks send document text to the Anthropic
  API only when `ANTHROPIC_API_KEY` is set.
- A real `.pdf` test for `docassert extract`.

## [0.4.0] — 2026-07-02

### Added
- The **doc-to-pmo Claude skill** ships with the package; `docassert init` now
  also scaffolds it into `.claude/skills/` so Claude Code discovers it.

### Changed
- The skill rewritten for the current model: all authorable kinds, project
  anchors, `docassert extract` / `docassert new`, item + typed-link grammar,
  TODO-flagging, and a confidentiality guardrail.

## [0.3.0] — 2026-07-01

### Added
- `docassert new <kind> --project PRJ-NNN-CODE` — scaffold a document from its
  template with identity filled in; `new project --code XYZ` auto-numbers the
  id; prints the next free item id per item type.

### Changed
- Templates now carry a `project:` placeholder and `<CODE>-<slug>` ids, so
  hand-copies match the schemas.

## [0.2.1] — 2026-07-01

### Fixed
- Exit codes are capped at 125 so large blocking-failure counts can't wrap the
  8-bit exit status (256 failures no longer read as success in CI).
- Every document-reading command accepts `--documents-dir` (the tree was
  previously hardcoded to `./documents`).
- AI alignment grading is capped per run (`alignment_limit`, default 25) so
  API cost is bounded on large graphs.
- CI tests the full supported matrix (Python 3.10–3.13).

## [0.2.0] — 2026-07-01

### Added
- `docassert extract <file>` — plain text from `.docx` / `.pdf` / `.md` /
  `.txt`, the first step of doc-to-pmo conversion (needs the `convert` extra).

### Removed
- `tools/extract.py` (superseded by the command).

## [0.1.0] — 2026-07-01

Initial release: `validate`, `consistency`, `rtm`, `status`, `pages`,
`projects`, `init`; packaged default criteria / schemas / profiles / templates
resolved local-override → packaged-default; Apache-2.0.
