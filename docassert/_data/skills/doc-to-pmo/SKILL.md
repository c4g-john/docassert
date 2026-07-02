---
name: doc-to-pmo
description: Convert an existing business document (Word .docx, PDF, or pasted text) into a docassert Markdown document so it can be unit-tested and gated in CI. Use when someone wants to bring an existing charter, BRD, PRD, risk register, or any other supported kind into a PMO-as-Code repo.
---

# doc-to-pmo

Convert a source document into a standard docassert document. **Map the content
faithfully — never invent missing facts to make the audit pass.** A document
that lacks measurable success criteria *should* fail the audit; your job is to
surface that, not hide it.

Requires docassert (`pipx install docassert`; add `"docassert[convert]"` for
.docx/.pdf extraction).

## Steps

1. **Identify the kind.** Supported kinds: `charter`, `business-case`, `brd`,
   `prd`, `frnfr`, `user-story`, `test-cases`, `adr`, `risk-register`,
   `raci-stakeholder`, `qa-test-plan`, `data-migration-plan`,
   `release-cutover-plan`, `rollback-plan`, `hypercare-plan`, `runbook`,
   `status-report`, `post-implementation-review`, `benefits-realization`.
   One source file may yield several documents (a "BRD" is often really a
   BRD + PRD + NFRs + risks). Propose the split to the user before writing.

2. **Anchor the project.** Every document belongs to a project
   (`PRJ-NNN-CODE`). Check `projects.yaml` or `documents/` for an existing
   anchor; if there is none, create one (ask the user for the code, name, and
   sponsor — don't guess):

   ```bash
   docassert new project --code AUR --name "Aurora — Customer Onboarding"
   ```

3. **Extract the source text** (`.docx`, `.pdf`, `.md`, `.txt`):

   ```bash
   docassert extract path/to/source.docx
   ```

   For pasted text or Google Docs, ask the user to paste the content or export
   to `.docx`/`.pdf` first.

4. **Scaffold, then fill.** Let docassert create the file with the identity
   (frontmatter `project:`, namespaced `id:`) already correct, then map the
   source content into its sections:

   ```bash
   docassert new brd --project PRJ-001-AUR
   # docassert: created documents/PRJ-001-AUR/brd.md
   # docassert: next item id: AUR-BR-001
   ```

   Keep `status: draft` unless the source clearly states an approval.

5. **Author traceable items where the kind defines them.** Requirements,
   criteria, tests, risks, and decisions are bullets with a stable namespaced
   id and typed links — use the `next item id` hints for numbering:

   ```
   - **AUR-BR-001**: The business shall reduce onboarding time to under 2 days.
   - **AUR-PR-001** (traces: AUR-BR-001): The product shall provide a self-serve flow.
   - **AUR-RISK-001** (threatens: AUR-BR-001): Migration may slip. Probability: High.
     Impact: High. Owner: alex.kim. Response: dual-run for two weeks.
   ```

   Relations: `traces` (child → parent requirement), `verifies` (AC → PR/FR),
   `tests` (TC → AC), `threatens` (RISK → BR/PR), `affects` (ADR → FR/NFR).
   Only link items that genuinely relate in the source.

6. **Flag gaps honestly.** Wherever the source does not supply required
   information, insert a bullet or note beginning with `TODO:` describing what
   is missing (e.g. `- TODO: no measurable success criteria found in the
   source — add a metric and threshold.`). Do **not** fabricate a number, an
   owner, a date, or a mitigation.

7. **Validate and report.**

   ```bash
   docassert validate documents/PRJ-001-AUR/*.md
   docassert consistency
   ```

   Summarise what passed, what blocks, and exactly which TODOs the user must
   resolve before the document can merge.

8. **Hand off.** Tell the user to review the generated files, resolve the
   TODOs, then commit and open a pull request — CI re-runs the same audit and
   gates the merge.

## Guardrails

- **Faithful over passing**: it is correct and expected for a weak source to
  produce a document that fails the audit. That is the pipeline working.
- Never invent approvals, owners, budgets, dates, or measurable thresholds.
- Never mark a document `approved`; that is a human decision made in review.
- If you are unsure whether something in the source is a real measurable
  criterion, leave it as written and let the audit judge it.
- Confidential sources stay local: don't push converted content to a public
  repo without the user's say-so.
