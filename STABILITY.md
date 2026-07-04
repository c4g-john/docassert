# Stability and deprecation policy

docassert versions follow [SemVer](https://semver.org/). This document states
what that promise covers from 1.0 onward, and how deprecations happen. It
exists because adopters gate merges on this tool: nothing it guarantees may
change out from under a pinned CI job.

## What 1.x guarantees

**The CLI surface.** Every command and flag in the reference below. New
commands and flags may be added in minor versions; none are renamed or
removed except by the deprecation process, and never before a major version.

**Machine-readable output shapes.** The JSON report (`--json`), bridge status
JSON, the badge endpoint payloads, and `projects.yaml`. Fields may be added
in minor versions; fields are never removed or retyped before a major.
Human-readable output (console text, markdown, HTML) is not covered — its
wording and layout may change in any release.

**Exit-code semantics.** Zero for a clean gate, non-zero for blocking
failures; advisory findings never affect exit codes.

**Packaged data semantics.** The packaged schemas, criteria, profiles, and
templates track the [PMO as Code spec](https://github.com/c4g-john/pmo-as-code-spec);
behavior-affecting changes to them land spec-first and are called out in the
changelog. A repository-local copy of any packaged file always wins.

**The spec relationship.** Each release states which spec version it
implements, and the conformance suite runs in CI at that spec tag. A
gate-observable behavior change without its specification text does not merge.

## How deprecations happen

1. Announced in the changelog under **Deprecated**, with the replacement named.
2. The deprecated surface keeps working for at least one further minor
   release, emitting a warning where practical.
3. Removal happens only in the next major version, listed under **Removed**.

## CLI reference

Generated from the live argument parser; regenerate with the release process
so this list cannot drift from the code.

### `docassert bridge`

usage: docassert bridge [-h] [--repo REPO] [--project PROJECT]
                        [--docs-url DOCS_URL] [--dry-run] [--json] [--out OUT]
                        [--title TITLE] [--project-owner PROJECT_OWNER]
                        [--project-number PROJECT_NUMBER] [--init-board]
                        [--board-token-env BOARD_TOKEN_ENV]
                        [--documents-dir DOCUMENTS_DIR]
                        {scaffold,reconcile,status,create-board}

| Flag / argument | Meaning |
|---|---|
| `action` | scaffold: docs -> issues/board · reconcile: police the board · status: delivery figures. |
| `--repo` | Target GitHub repo (OWNER/NAME) for the whole plan; omit to route each project to the `repo:` on its anchor. |
| `--project` | Scope to one project (PRJ-NNN-CODE id or CODE). |
| `--docs-url` | Base URL of the documents repo, for source links in issue bodies. |
| `--dry-run` | Print planned mutations without executing them. |
| `--json` | status: emit JSON. |
| `--out` | status --json: also write to this path. |
| `--title` | create-board: the new project's title. |
| `--project-owner` | Board owner login (default: the repo owner). |
| `--project-number` | Projects v2 board number to sync items onto. |
| `--init-board` | Ensure the Type/Doc/PMO Project fields exist. |
| `--board-token-env` | Env var holding the project-scoped token (default: PROJECTS_TOKEN). |
| `--documents-dir` | Documents tree to read (default: documents/). |

### `docassert consistency`

usage: docassert consistency [-h] [--junit JUNIT] [--markdown MARKDOWN]
                             [--json JSON] [--no-semantic]
                             [--documents-dir DOCUMENTS_DIR]

| Flag / argument | Meaning |
|---|---|
| `--junit` | Write a JUnit XML report to this path. |
| `--markdown` | Write a PR-comment markdown report to this path. |
| `--json` | Write a machine-readable JSON report to this path. |
| `--no-semantic` | Skip AI alignment (structural consistency only). |
| `--documents-dir` | Documents tree to read (default: documents/). |

### `docassert extract`

usage: docassert extract [-h] [--out OUT] file

| Flag / argument | Meaning |
|---|---|
| `file` | Source document (.docx / .pdf / .md / .txt). |
| `--out` | Write to this path instead of stdout. |

### `docassert init`

usage: docassert init [-h] [dir]

| Flag / argument | Meaning |
|---|---|
| `dir` | Target directory (default: current). |

### `docassert new`

usage: docassert new [-h] [--project PROJECT] [--code CODE] [--name NAME]
                     [--out OUT] [--documents-dir DOCUMENTS_DIR]
                     kind

| Flag / argument | Meaning |
|---|---|
| `kind` | Document kind (e.g. charter, brd, project). |
| `--project` | Owning project id, PRJ-NNN-CODE (for `new project`: the id to create). |
| `--code` | For `new project`: 2–6 letter code; the sequence number is auto-picked. |
| `--name` | For `new project`: the project name. |
| `--out` | Write to this path instead of the default location. |
| `--documents-dir` | Documents tree to read (default: documents/). |

### `docassert pages`

usage: docassert pages [-h] [--out OUT] [--execution EXECUTION]
                       [--documents-dir DOCUMENTS_DIR]

| Flag / argument | Meaning |
|---|---|
| `--out` | Output directory (default: _site). |
| `--execution` | Optional bridge-status JSON; adds Delivery and Scope panels to project pages. |
| `--documents-dir` | Documents tree to read (default: documents/). |

### `docassert projects`

usage: docassert projects [-h] [--out OUT] [--check]
                          [--documents-dir DOCUMENTS_DIR]

| Flag / argument | Meaning |
|---|---|
| `--out` | Write to this path instead of stdout (e.g. projects.yaml). |
| `--check` | Exit non-zero if the registry file is stale (CI freshness gate). |
| `--documents-dir` | Documents tree to read (default: documents/). |

### `docassert rtm`

usage: docassert rtm [-h] [--out OUT] [--csv] [--project PROJECT]
                     [--documents-dir DOCUMENTS_DIR]

| Flag / argument | Meaning |
|---|---|
| `--out` | Write to this path instead of stdout. |
| `--csv` | Emit CSV instead of Markdown. |
| `--project` | Scope to one project (PRJ-NNN-CODE id or CODE). |
| `--documents-dir` | Documents tree to read (default: documents/). |

### `docassert status`

usage: docassert status [-h] [--format {md,json,html}] [--summary]
                        [--project PROJECT] [--index] [--out OUT]
                        [--documents-dir DOCUMENTS_DIR]

| Flag / argument | Meaning |
|---|---|
| `--format` | Output format (default: md). |
| `--summary` | Condensed markdown (RAG + signals, no inventory table). |
| `--project` | Scope the status to one project (its PRJ-NNN-CODE id). |
| `--index` | Render the multi-project portfolio index instead of one status. |
| `--out` | Write to this path instead of stdout. |
| `--documents-dir` | Documents tree to read (default: documents/). |

### `docassert validate`

usage: docassert validate [-h] [--junit JUNIT] [--markdown MARKDOWN]
                          [--json JSON] [--documents-dir DOCUMENTS_DIR]
                          paths [paths ...]

| Flag / argument | Meaning |
|---|---|
| `paths` | Markdown files or globs. |
| `--junit` | Write a JUnit XML report to this path. |
| `--markdown` | Write a PR-comment markdown report to this path. |
| `--json` | Write a machine-readable JSON report to this path. |
| `--documents-dir` | Documents tree to read (default: documents/). |

