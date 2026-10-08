---
name: audit-report
description: Build the audit deliverables (confidential peer report, plain-language summary of quick wins, remediation prompts) from verified findings, as the engagement's audience requires. Use after verify-findings, or when asked for the report of an audit workspace.
---

# audit-report

Version: 0.6.0 (audit skills, see CHANGELOG)

Turn the findings files into the deliverables the engagement asks for. A
report is a projection of the findings: it adds no analysis, and every claim
in it can be traced to a finding, a lead, a coverage line or the engagement
file.

Input: `00-engagement.md`, `01-codebase-map.md`, `findings/*.md`.
Output: `<workspace>/reports/`.

## Before starting

1. Read the engagement file, `finding-format` and every findings file.
2. **Stop if verification is missing.** Every finding must be `confirmed`,
   `refuted`, or `unverified` with a `**Verification.**` note saying why. A
   finding with no note has not been through `verify-findings`: run it first
   (in a separate context, as that skill requires).
3. Recompute every count from the files. Never copy a number from a previous
   summary.
4. **Consistency check.** For each finding: does the text agree with the YAML
   (rating stated in prose, remediation still valid after the verification
   note)? Are all citations openable by the reader? Do the installed audit
   skills report the same `Version:`? Collect every discrepancy.
5. If the list is not empty, write the deliverables anyway but mark each one
   **DRAFT** at the top, with the list, and hand over to `verify-findings` in
   revision mode. Regenerate after it has run. A deliverable is final only when
   the list is empty. Never fix a discrepancy in the report itself.

## Which deliverables

| Engagement says | Produce |
|---|---|
| `readers` includes `peer` | `reports/peer-report.md` (confidential) |
| `readers` includes `non-technical` | `reports/summary.md` |
| `prompt_executor` is not `none` | `reports/remediation-prompts.md` |

Write them in the engagement's `language`. Headings are free here: reports are
for people, not for other skills.

## Common header

Every deliverable starts with the same provenance block, so a reader can tell
what it covers and what produced it:

- target, commit audited, dates of the audit;
- axes requested, and for each: evaluated, partial, not evaluable or not
  requested;
- testing regime (passive or active, on which hosts);
- skills version actually used (the `Version:` line of each audit skill, and
  the engagement file's value if it differs) and tools used;
- confidentiality: "confidential" on the peer report and the prompts.

## Peer report

For a technical reader who will act on it or challenge it. Complete.

1. **Summary**: counts of confirmed findings by severity and axis; quick wins
   (as `finding-format` defines them); the two or three findings that matter
   most, with one sentence each on why.
2. **Scope and coverage**: per axis, the coverage table from its findings
   file, including what was not evaluated and why. A gap must be as visible as
   a finding.
3. **Findings**, by axis, then severity, then effort. For each confirmed
   finding: title, ID, rating line (severity, confidence, effort, evidence
   regime), evidence, technical explanation, remediation, and the
   verification note condensed to what it established.
4. **Not verified**: findings left `unverified`, each with the reason and who
   can settle it. Never mixed with confirmed ones.
5. **Accepted**: confirmed findings with `resolution: accepted`, each with the
   owner's decision and date. Not counted among quick wins.
6. **Open leads and questions**: every lead with status `open`, and every
   question for the auditor, with what each would change, and the answers
   already received.
7. **Refuted**: one line each (ID, title, why). It shows the audit checked its
   own work.
8. **Method and limits**: how the codebase was mapped, where dependency code
   came from, what the running target was, the unknowns from the map that
   still stand.

## Plain-language summary

For a decision maker who will not read code. Two pages at most.

1. **What was looked at, and what was not.** One paragraph. Say plainly which
   axes were not audited: a summary that only covers security must not read
   as a clean bill of health.
2. **The overall picture**, in three to five sentences.
3. **Quick wins**: each as a short title in everyday words, why it matters
   (from the plain-language explanation), what fixing it involves, and who
   usually does it (developer, host, the association itself).
4. **To go further**: the confirmed findings that are not quick wins, grouped
   by theme, one or two sentences each.
5. **What we need from you**: the questions for the auditor that the owner
   can answer, rephrased without jargon.

Rules for this document:

- Only confirmed findings with `resolution: open`; accepted ones appear as a
  single line ("N points were reviewed and kept as they are, by decision").
  No IDs in the text; put them in a short table at the end so a developer can
  find the detail.
- A `sensitive` finding is described by its consequence only: no file, entry
  point, parameter, host or method. The detail stays in the peer report.
- No severity labels without their meaning; explain the scale in one line if
  you use it.

## Remediation prompts

One prompt per confirmed, `promptable` quick win, then one per other
confirmed `promptable` finding if the auditor asked for all of them. Each
prompt is self-contained: whoever pastes it into a coding agent has nothing
else.

Shape depends on `prompt_executor`:

- `executable`: written to a coding agent working in the repository. Context
  (stack, files concerned, repository-relative paths), the change wanted as a
  target behaviour, constraints (what must not change, conventions to follow),
  and the acceptance check from the finding's remediation, as a test to write
  or a command to run.
- `vendor-brief`: the same content, written to a developer: what to change,
  why in one sentence, how to check it is done.
- `both`: both forms for each finding.

What a prompt never contains, whatever the finding: how the weakness could be
exploited, a payload, a secret, personal data, a production host or URL.
Prompts are made to be pasted into third-party tools; they describe the
target state, not the attack.

Findings that are quick wins but not `promptable` (rotate a key, set a
variable at the host, record a decision) go in a final section, "To do by
hand", with who does it and how to check.

## Rules

**Nothing new.** If writing the report reveals a gap (a finding without
plain-language explanation, a contradiction between two findings), stop and
fix the findings file through the right skill, or list it under "Method and
limits". Do not patch it in the report.

**One source of truth.** If a finding changes after the report was written,
regenerate the report; never edit the report by hand to match.

**Check before handing over.** Every ID cited exists and has the status the
report gives it; counts match the files; no sensitive detail appears in the
summary or the prompts; every requested deliverable exists. Say in the end
message that this check was done and what it found.

## End message

List the files produced, the counts (confirmed by severity, quick wins,
unverified, refuted, open leads), and the questions waiting for the auditor.
