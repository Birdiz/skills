---
name: verify-findings
description: Try to refute every unverified audit finding from a context that did not produce it, and set each one to confirmed, refuted, or left unverified with a reason. Use after the axes of an audit have run, before any report, or when findings files contain unverified findings.
---

# verify-findings

Version: 0.24.0 (audit skills, see CHANGELOG)

The only step that sets `status` to `confirmed` or `refuted`; everything
downstream stands on it. Input: `00-engagement.md`, `01-codebase-map.md`,
`findings/*.md`, the working copy. Output: the findings files, updated in
place. Bound by [rules of engagement](../finding-format/rules-of-engagement.md).

## Independence

An agent re-reading its own reasoning finds it convincing, so the verifier is
a context that wrote none of the findings: a sub-agent given file paths only
(workspace, working copy, this skill), never the conversation or a summary;
facts about the environment (tools available, a browser that cannot open a
host, a constraint on images) may be added, nothing about the findings.
Without sub-agents, if this session wrote a finding, stop and tell the auditor
to invoke `verify-findings` in a new session: a blocker. Each note records `by:
sub-agent | new session`.

## Per finding

Refute: ask what would make the finding wrong; confirm only once every answer
has been checked and failed. Take every `unverified` finding, file by file,
by severity within each file, and save each file as soon as it is done. A
finding that already has a `verification` key was verified before (an
interrupted run resumes this way) and is skipped, outside revision mode
and fix checks, unless an `**Auditor answer.**` is dated after that key and no
`Re-checked …, answer of <that date>` line of the note covers it: then
only what the answer changed is re-checked (its reason, its pointer, the
rating against the axis's current grid, its references), and the
`**Verification.**` paragraph gets one line. When the re-check corrects
nothing, the line is `Re-checked YYYY-MM-DD, answer of YYYY-MM-DD: no
change.`, in English whatever the note's language, and `on` stays, so the
plan is not made stale for nothing; when it corrects something, the line says
what, and `on` takes the re-check's date. Earlier lines of the note stay as
history; the new line names any value it supersedes. Leads are
spot-checked only where the answers re-checked closed them.

Before replaying anything on the running target, check which commit it
serves and which image runs it. A target that no longer exists replays
nothing: its dynamic evidence stands as recorded, and the note says so. Data on the target may have changed since the axis ran (fixtures
reloaded, another step's creations): re-observe with current identifiers and
say so in the note.

1. **Reproduce.** Open each location at the audited commit; rerun the evidence
   commands the rules allow; a quote shows a drifted line at a glance, and
   must be found at its pointer (a sentence cited from a file that does not
   contain it is corrected). Check what each count in the evidence actually
   matched. A pointer that does not match settles it: refute or correct.
2. **Find the control elsewhere**: framework defaults, global listeners,
   middleware or config, an upstream check, infrastructure in the repository,
   read in the dependency code the map names (its install rechecked) rather
   than recalled; and the owner's own documentation of known limits and
   planned work, which the finding must cite. An install that no longer
   matches the audited lock is not read: the note says what it could not
   check, for `recon`.
3. **Reachability**: who, through which entry point, under which conditions;
   an unmentioned check may leave it real but lower.
   For `code-quality` and `architecture`: the code is on the flow the finding
   names, and the claimed cost is shown (history, diverged copies, a failure
   path); a preference is refuted. A cost the audit itself met counts when
   any newcomer to the code would meet it too.
   For a declarative finding: the answer is recorded under its question,
   dated, and says what the finding quotes; nothing in the repository or on
   the target contradicts it; the consequence follows from it. The owner's
   statement is not re-asked: what only the owner knows is taken as
   answered. Scanners are rerun on the axis's vulnerability database, not
   updated, its date recorded.
4. **Rating**: severity against the axis grid; a stated adjustment holds
   only if its reason holds at its pointer (a sound move on a wrong reason is
   kept, the reason rewritten); confidence; `sensitive` and `promptable`
   against `finding-format`; references against their source, each
   openable (`finding-format`, Evidence): an undated one gets a copy in
   the workspace whose run output gives its fetch date.
5. **Decide**:
   - `confirmed`: evidence reproduced, no control, reachability as stated;
     a wrong rating is corrected;
   - `refuted`: evidence fails, or a control fully prevents the consequence;
   - `unverified`: beyond the engagement's capabilities, or only the auditor
     or owner can settle it. Facts reproduced with a rating that depends on
     an answer (a setting not seen, a decision not taken) are `confirmed`,
     the condition stated and its question asked.

## Writing the result

Each finding gets a `**Verification.**` paragraph after `**Remediation.**` and
two keys:

```yaml
status: confirmed
verification: {by: sub-agent, on: 2026-10-08}
```

```markdown
**Verification.** by: sub-agent, verify-findings@0.13.0, tools: [git@2.50.1].
Reproduced: src/Security/UserChecker.php:20-25 and the
listener priorities (vendor/...:56, vendor/...:94). No global control found.
Severity kept at medium.
```

**Correct in place** whatever was proven wrong (pointer, claim, scenario,
remediation, reference, the plain-language explanation), quoting the
replaced text in the note; reports read these files. A corrected fact
repeated elsewhere is corrected there too: the coverage, a question, a
text the axis wrote in `tool-output/` that findings cite (an inventory),
never a raw tool output. A coverage statement found wrong on its own is
annotated with the pointer. A question the repository already answers is
annotated with the pointer. The rest stays as written.

- Refuted: what makes it wrong, with pointers.
- Rating changed: old value, new value, reason; the YAML and every sentence
  stating the old value updated.
- Text corrected: the old passage and what proved it wrong.
- Unverified: what is missing, who can settle it, and an entry in `##
  Questions for the auditor`.
- Findings with one cause that do not cite each other: the citation added
  to both technical explanations.

## Revision mode

Discrepancies listed by `audit-report` or the auditor in verified findings
(text against YAML, unapplied corrections, unopenable citations), and the
blocking items of the latest report that name this step, are applied
in place under the same rules, `confirmed` findings included. Re-check only
what the correction touches; add one line to the note, `Revised
<YYYY-MM-DD>: <what>.`, and move `on` (a correction, not a re-check). A
note citing the report names it by its run folder, which a later report
does not reuse.

## Fix checks

When the auditor asks, or `tickets` names fixes for `verify-findings` on a
later commit (closed in tracker, possibly done), this step checks whether
those fixes' findings are fixed at that commit: the head of the tracker's
default branch when the run starts, its full SHA recorded in the run's
folder. It is read in a clone made for it, `<workspace>/repo-<short sha>/`,
detached, never in the audited working copy. A finding's text, rating and
`status` stay as written: they describe the audited commit.

The test is the finding's remediation and its fix's Check, every part and
every case, read at that commit, with the commits and pull requests that
changed it. The rules of engagement hold: the project never runs, but a
command that only parses its files and starts nothing (a configuration
resolved) may, its output masked; dependency code comes from an install
matching that commit's lock, else from copies pinned to the locked
commits, fetched into the run's folder with their date. A part only the
running target shows, with no target serving that commit, is not
observable: it remains.

- Every part and case holds: `resolution: fixed`.
- Some do: `open`, in part, saying what is done and what remains.
- None does: `open`, not fixed.

A case the remediation or the Check covers that the later code misses (an
input the new code does not handle) is what remains, never a lead. A
defect outside them, in code the audited commit does not have, is neither
a lead nor a finding of this engagement: one line in the end report,
`seen at <short sha>, outside this engagement`, for the auditor and a
later engagement.

The note gets one line, its parsed part in English: `Fix checked
<YYYY-MM-DD> at <short sha>: fixed by <commits> (PR #<n>).`, `…: in part:
<done>; remains <what>.` or `…: not fixed.`, then what was read, pointers
at that commit written `<short sha>:<path>:<line>`. `on` takes the check's
date whatever the outcome, so the plan sees it. A `fixed` that a report or
the auditor questions is checked again, in revision mode, by the same
test. Nothing else of this skill runs in this mode: leads are not
spot-checked or moved, coverage is unchanged.

## Leads

Open leads are left to their axis, uninvestigated. Spot-check, in the files
whose findings you verify, the `closed` ones with the weakest reasons, and
every one closed as declared (the answer says what the closure claims, and
the repository does not contradict it). A wrong closure goes back to
`open:` with the reason; a right closure on a wrong reason keeps its status,
the reason rewritten; one that rests on an answer without saying so takes
the declared form. A check that held is one line in the note of the axis. Anything new becomes a lead for its axis, `open: from verify-findings
<YYYY-MM-DD>; <who settles it>`, which the validator lists for a lead
pass: a finding written by the verifier would have no verifier.

Once every finding is decided, work through the files in turn (the verifier
is the one step that reads them all, alone):

1. Move each bullet under `## Leads for other axes`, whatever its shape,
   into its target axis's `## Leads`, with the next free ID there, a title,
   and the status `finding-format` gives a moved lead; the bullet is
   replaced by `moved to L-…`. A lead closed although its consequence
   belongs to another axis is moved the same way. A moved lead that a
   confirmed finding's locations already cover is closed as settled by it,
   with the pointer.
2. Rewrite the leads that confirmed findings say they settle, in the lead's
   own file: `closed: settled by F-…`, or for a part `open: <part> settled
   by F-…; remains <what>, <who>`. A refuted finding settles nothing.
3. List the axes that received leads after they ran: each needs a lead pass
   (`finding-format`, Leads).

Last, run the validator (`finding-format`, Validator) with `--require
verification`, its output kept in `tool-output/verify/`. Its errors in
what this step wrote, and answer marks out of form whose date and words
leave no doubt (`finding-format`, Questions and answers), are fixed in
place, and questions without ID numbered in the files this step writes;
the others go in the end report, for the step that owns them. Its
`lead-pass` lines are the axes of step 3.

## End report

Per axis: confirmed, refuted, unverified, ratings changed, text corrected,
leads reopened, moved, or closed as settled; then the questions added, the
citations added between findings with one cause, the marks put in form
(each old mark quoted), and the axes that need a lead pass; fix checks:
the commit, each finding fixed, in part (what remains) or not fixed, and
what was seen outside this engagement; the findings whose text changed that a report or a ticket
already carries, so the next `audit-report` and `tickets` take them up.
Continue with those lead passes, or with `remediation-plan` when a plan
exists, then `audit-report`.
