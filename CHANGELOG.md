# Changelog

All notable changes to docassert. Format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [SemVer](https://semver.org/).

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
