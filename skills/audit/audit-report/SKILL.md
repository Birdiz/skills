---
name: audit-report
description: Build the audit deliverables (confidential peer report, plain-language summary of quick wins, remediation prompts) from verified findings, as the engagement's audience requires. Use after verify-findings, or when asked for the report of an audit workspace.
---

# audit-report

Version: 0.16.0 (audit skills, see CHANGELOG)

A report is a **projection** of the findings: every claim traces to a finding,
a lead, a coverage line, a fix of the plan or the engagement file. Input:
`00-engagement.md`, `01-codebase-map.md`, `02-remediation-plan.md`,
`findings/*.md`. Output: `<workspace>/reports/`.

## Before writing

1. Read the engagement file, `finding-format`, every findings file.
2. **Verification present**: every finding `confirmed`, `refuted`, or
   `unverified` with a `**Verification.**` note, and none changed by an
   `**Auditor answer.**` dated after its note. Any other goes to
   `verify-findings` first, in a separate context.
   **Plan current**: `02-remediation-plan.md` holds every confirmed open
   finding in exactly one open fix, and no other, and is not stale
   (`remediation-plan`, Before starting); otherwise it goes to
   `remediation-plan` first.
3. **Recompute** every count from the files, with a script kept in
   `tool-output/report/`.
4. **Consistency check** per finding: text agrees with the YAML (prose rating,
   remediation still valid after the note); citations open for the reader
   (a file in the repository or the workspace, a versioned or dated public
   URL, or an undated one with a copy in the workspace whose run output
   gives its fetch date; a URL of the
   running target, in evidence or `locations`, is evidence of its day, not a
   citation); each step's skill version, recorded in its output or
   attributed by the engagement file, agrees with that file;
   each axis's status, derived as `finding-format` says from its areas,
   agrees with what the areas state. Per fix: its reason for grouping is
   stated with a pointer; its change agrees with each finding's
   remediation; its check holds each finding's check, so a test written
   from it fails before the fix; its `severity`,
   `promptable` and `sensitive` follow from its findings.
5. **Sort discrepancies.** *Blocking*: something a reader acts on or judges
   by is wrong or unreadable: a remediation stale or incomplete; a rating,
   `sensitive`, `promptable` or claim contradicted by the finding's own
   text, `finding-format`, its note or
   an answer; findings with one cause at odds on the fix; a fix that drops
   a finding's check or contradicts its remediation; an unopenable
   citation; a step whose recorded version contradicts the engagement file;
   an area status that breaks `finding-format` (evaluated while waiting for
   an answer). Versions that differ between steps, each recorded or
   attributed, are provenance, not a discrepancy. *Cosmetic*: form only, or
   stale without changing a judgment (label or prose language, wording, a
   lead ID cited after its promotion, a coverage sentence a later pass made
   stale, findings with one cause and compatible fixes that do not cite each
   other, an axis plan the coverages since moved), listed under "Method and
   limits" and fixed at the next revision.
6. **Draft** while a blocking one remains: deliverables open with `DRAFT`
   and the list, each item naming who fixes it, in order when several do: `verify-findings` in
   revision mode for the findings' text, the axis's lead pass for its
   coverage, `remediation-plan` for the plan, `audit-kickoff` for the
   engagement file. The end message asks
   for those steps, then a new report.

Fixes happen in the findings files, through the skill that owns them, and the
report is regenerated; a finding changed after the report means a new report,
never a hand edit. This step edits no findings file: a gap found while
writing (a missing plain-language explanation, two findings at odds) is a
discrepancy, sorted as above.

## Deliverables

- `readers` includes `peer`: `reports/peer-report.md` (confidential).
- `readers` includes `non-technical`: `reports/summary.md`.
- `prompt_executor` other than `none`: `reports/remediation-prompts.md`.

Structure of each: [deliverables.md](deliverables.md). Written in the
engagement's `language`, headings free.

Each opens with the same provenance: target, audited commit, audit dates;
every axis with its status as `finding-format` derives it (evaluated,
partial with its partial areas, not evaluable, not requested), and the
status its file records when it differs; testing regime
and hosts; what was created on the target; tools, and the version of each
skill as each step recorded it; "confidential" on the peer report and
prompts.

## Handing over

Check that every cited ID exists with the status given, counts match the
files, the summary and prompts carry no sensitive detail, and every requested
deliverable exists. The end message says what the check found, lists the
files, the counts (confirmed by severity, fixes by executor, quick-win
fixes, unverified, refuted, open leads) and the questions waiting:
unanswered, never asked, and answered but undecided.
