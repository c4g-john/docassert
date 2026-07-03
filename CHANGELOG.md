# Changelog

All notable changes to docassert. Format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [SemVer](https://semver.org/).

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
