---
name: audit-report
description: Build the audit deliverables (confidential peer report, plain-language summary of quick wins, remediation prompts) from verified findings, as the engagement's audience requires. Use after verify-findings, or when asked for the report of an audit workspace.
---

# audit-report

Version: 0.24.0 (audit skills, see CHANGELOG)

A report is a **projection** of the findings: every claim traces to a finding,
a lead, a coverage line, a fix of the plan or the engagement file. Input:
`00-engagement.md`, `01-codebase-map.md`, `02-remediation-plan.md`,
`findings/*.md`. Output: `<workspace>/reports/`.

## Before writing

1. Read the engagement file, `finding-format`, every findings file, the
   plan, and the codebase map's header (commit, tools, skill).
2. **Verification present**: every finding `confirmed`, `refuted`, or
   `unverified` with a `**Verification.**` note, and none with an
   `**Auditor answer.**` dated after its note that the note has not
   re-checked. Any other goes to `verify-findings` first, in a separate
   context.
   **Plan current**: `02-remediation-plan.md` holds every confirmed open
   finding in exactly one open fix, and no other, and is not stale
   (`remediation-plan`, Before starting); otherwise it goes to
   `remediation-plan` first.
   The validator (`finding-format`, Validator), run with `--require
   verification --require plan`, its output kept in this run's folder
   (`tool-output/report/`, or a later run's folder as the rules of
   engagement name it), checks both; its other errors are discrepancies
   (step 5): cosmetic when the form alone is wrong (a mark, a label),
   blocking otherwise.
   **Engagement current**: when a step ran since `audit-kickoff` last
   copied versions and tools (an earlier report or tickets run
   included; this run records itself in its own provenance), this step
   makes that copy itself first, as `audit-kickoff` (After confirmation,
   step 7) says, dated, keeps the file as it was beside its scripts as
   `00-engagement.before.md`, and says so in the provenance.
   **Inputs**: the sha256 of the plan and of each findings file, kept in
   this run's folder as `inputs.sha256` (`sha256sum` format, paths
   relative to the workspace), with a copy of those files under
   `inputs/`; the provenance names that folder in an English line,
   `run: tool-output/report/<run>/`, where `tickets` reads the hashes and
   the validator output.
3. **Recompute** every count from the files, with a script kept in
   this run's folder.
4. **Consistency check** per finding: text agrees with the YAML (prose rating,
   remediation still valid after the note); citations open for the reader
   (a file in the repository or the workspace, a `<short sha>:` pointer
   in the clone of that commit a fix check made, a versioned or dated public
   URL, or an undated one with a copy in the workspace whose run output
   gives its fetch date; a URL of the
   running target, in evidence or `locations`, is evidence of its day, not a
   citation); each step's skill version, recorded in its output or
   attributed by the engagement file, agrees with that file;
   each axis's status, derived as `finding-format` says from its areas,
   agrees with what the areas state. A findings file whose hash matches
   the previous report's `inputs.sha256` keeps that report's judgments,
   and a plan whose hash matches keeps its per-fix judgments; in a file
   that differs, the findings and fixes whose text the previous report's
   `inputs/` copy shows unchanged keep theirs too; said under "Method and
   limits"; the rules changed since are checked on every one. Per fix:
   its reason for grouping is stated with a pointer; its
   change agrees with each finding's remediation; its check holds each
   finding's check, so a test written from it fails before the fix, and
   tests every part of the change, as `remediation-plan` (The plan)
   defines a part; in a
   fix that waits for something, a step its change says waits for
   nothing has its own check; its `locations` are where the change
   lands; its `severity`, `promptable` and `sensitive` follow from its
   findings.
5. **Sort discrepancies.** *Blocking*: something a reader acts on or judges
   by is wrong or unreadable: a remediation stale or incomplete; a rating,
   `sensitive`, `promptable` or claim contradicted by the finding's own
   text, `finding-format`, its note or
   an answer; a `resolution` its note's last fix check contradicts, or a
   `fixed` while a case its remediation names is shown missing at that
   commit; findings with one cause at odds on the fix; a fix that drops
   a finding's check, leaves a part of its change untested, or
   contradicts its remediation; a location a ticket cannot carry (a
   workspace path), or `locations` holding only evidence; a note relying
   on dependency code read from an install that no longer matches the
   audited lock; an unopenable
   citation; a step whose recorded version contradicts the engagement file;
   an area status that breaks `finding-format` (evaluated while waiting for
   an answer). Versions that differ between steps, each recorded or
   attributed, are provenance, not a discrepancy. *Cosmetic*: form only, or
   stale without changing a judgment (label or prose language, wording, a
   lead ID cited after its promotion, a coverage sentence a later pass made
   stale, findings with one cause and compatible fixes that do not cite each
   other, an axis plan the coverages since moved, a location that is
   evidence rather than where the change lands, or a place the change
   names missing from `locations`, when the change names where it lands;
   the map's install drifted with no note relying on it, for `recon`),
   listed under "Method and limits" and fixed at the
   next revision.
6. **Draft** while a blocking one remains: deliverables open with `DRAFT`
   and the list, numbered, each item naming by ID the findings and fixes
   whose text it could change, and ending with its own line `Holds: R-…, R-…`
   (or `Holds: nothing`), in English, that `tickets` reads: every fix holding one of
   those findings, a change that depends on what the step finds included.
   A finding the item could create holds no fix yet: a ticket it later
   joins shows as changed since sent. Each item names who fixes
   it, in order when several do: `verify-findings` in revision mode for
   the findings' text, the axis's lead pass for its coverage,
   `remediation-plan` for the plan, `audit-kickoff` for the engagement
   file. The end message asks for those steps, then a new report.

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
engagement's `language`, headings free. A previous report is moved to
`reports/superseded-<its date>/` (`-2`, `-3`… when that folder exists)
before writing, never overwritten; the hand-over check leaves those
folders out.

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
files, the counts (confirmed open by severity, fixed, fixes open by
executor and done, quick-win fixes, unverified, refuted, open leads) and the questions waiting:
unanswered, never asked, and answered but undecided.
