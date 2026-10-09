---
name: audit-report
description: Build the audit deliverables (confidential peer report, plain-language summary of quick wins, remediation prompts) from verified findings, as the engagement's audience requires. Use after verify-findings, or when asked for the report of an audit workspace.
---

# audit-report

Version: 0.10.0 (audit skills, see CHANGELOG)

A report is a **projection** of the findings: every claim traces to a finding,
a lead, a coverage line or the engagement file. Input: `00-engagement.md`,
`01-codebase-map.md`, `findings/*.md`. Output: `<workspace>/reports/`.

## Before writing

1. Read the engagement file, `finding-format`, every findings file.
2. **Verification present**: every finding `confirmed`, `refuted`, or
   `unverified` with a `**Verification.**` note. A finding without one goes
   to `verify-findings` first, in a separate context.
3. **Recompute** every count from the files.
4. **Consistency check** per finding: text agrees with the YAML (prose rating,
   remediation still valid after the note); citations open for the reader;
   installed audit skills share one `Version:`.
5. **Sort discrepancies.** *Blocking*: something a reader acts on is wrong or
   unreadable (stale remediation, rating or `promptable` contradicted by text
   or answer, unopenable citation, mixed skill versions). *Cosmetic*: form
   only (label or prose language, wording), listed under "Method and limits"
   and fixed at the next revision.
6. **Draft** while a blocking one remains: deliverables marked DRAFT at the
   top with the list, handed to `verify-findings` in revision mode, then
   regenerated.

Fixes happen in the findings files, through the skill that owns them, and the
report is regenerated; a finding changed after the report means a new report,
never a hand edit. A gap found while writing (a missing plain-language
explanation, two findings at odds) is fixed there or listed under "Method and
limits".

## Deliverables

- `readers` includes `peer`: `reports/peer-report.md` (confidential).
- `readers` includes `non-technical`: `reports/summary.md`.
- `prompt_executor` other than `none`: `reports/remediation-prompts.md`.

Structure of each: [deliverables.md](deliverables.md). Written in the
engagement's `language`, headings free.

Each opens with the same provenance: target, audited commit, audit dates;
every axis with its status (evaluated, partial, not evaluable, not requested);
testing regime and hosts; tools, and the `Version:` of each skill actually used
(plus the engagement file's value if it differs); "confidential" on the peer
report and prompts.

## Handing over

Check that every cited ID exists with the status given, counts match the
files, the summary and prompts carry no sensitive detail, and every requested
deliverable exists. The end message says what the check found, lists the
files, the counts (confirmed by severity, quick wins, unverified, refuted, open
leads) and the questions waiting for the auditor.
