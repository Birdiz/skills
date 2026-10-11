---
name: verify-findings
description: Try to refute every unverified audit finding from a context that did not produce it, and set each one to confirmed, refuted, or left unverified with a reason. Use after the axes of an audit have run, before any report, or when findings files contain unverified findings.
---

# verify-findings

Version: 0.12.0 (audit skills, see CHANGELOG)

The only step that sets `status` to `confirmed` or `refuted`; everything
downstream stands on it. Input: `00-engagement.md`, `01-codebase-map.md`,
`findings/*.md`, the working copy. Output: the findings files, updated in
place. Bound by [rules of engagement](../finding-format/rules-of-engagement.md).

## Independence

An agent re-reading its own reasoning finds it convincing, so the verifier is
a context that wrote none of the findings: a sub-agent given file paths only
(workspace, working copy, this skill), never the conversation or a summary.
Without sub-agents, if this session wrote a finding, stop and tell the auditor
to invoke `verify-findings` in a new session: a blocker. Each note records `by:
sub-agent | new session`.

## Per finding

Refute: ask what would make the finding wrong; confirm only once every answer
has been checked and failed. Take every `unverified` finding, by severity. A
finding that already has a `verification` key was verified before (an
interrupted run resumes this way) and is skipped, outside revision mode. Save
each findings file as soon as its axis is done.

Before replaying anything on the running target, check which commit it
serves. Data on the target may have changed since the axis ran (fixtures
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
   planned work, which the finding must cite.
3. **Reachability**: who, through which entry point, under which conditions;
   an unmentioned check may leave it real but lower.
   For `code-quality` and `architecture`: the code is on the flow the finding
   names, and the claimed cost is shown (history, diverged copies, a failure
   path); a preference is refuted. A cost the audit itself met counts when
   any newcomer to the code would meet it too.
4. **Rating**: severity against the axis grid; a stated adjustment holds
   only if its reason holds at its pointer (a sound move on a wrong reason is
   kept, the reason rewritten); confidence; `sensitive` and `promptable`
   against `finding-format`; references against their source.
5. **Decide**:
   - `confirmed`: evidence reproduced, no control, reachability as stated;
     a wrong rating is corrected;
   - `refuted`: evidence fails, or a control fully prevents the consequence;
   - `unverified`: beyond the engagement's capabilities, or only the auditor
     or owner can settle it.

## Writing the result

Each finding gets a `**Verification.**` paragraph after `**Remediation.**` and
two keys:

```yaml
status: confirmed
verification: {by: sub-agent, on: 2026-10-08}
```

```markdown
**Verification.** Reproduced: src/Security/UserChecker.php:20-25 and the
listener priorities (vendor/...:56, vendor/...:94). No global control found.
Severity kept at medium.
```

**Correct in place** whatever was proven wrong (pointer, claim, scenario,
remediation, reference), quoting the replaced text in the note; reports read
these files. A corrected fact repeated in the coverage is corrected there
too, and a question the repository already answers is annotated with the
pointer. The rest stays as written.

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
(text against YAML, unapplied corrections, unopenable citations) are applied
in place under the same rules, `confirmed` findings included. Re-check only
what the correction touches; add one line to the note saying what was revised
and when.

## Leads

Open leads are left to their axis, uninvestigated. Spot-check the `closed`
ones with the weakest reasons; a wrong closure goes back to `open:` with the
reason. Anything new becomes a lead for its axis: a finding written by the
verifier would have no verifier.

Once every finding is decided, work through the files in turn (the verifier
is the one step that reads them all, alone):

1. Move each bullet under `## Leads for other axes` into its target axis's
   `## Leads`, with the next free ID there, and leave `moved to L-…` in its
   place. A lead closed although its consequence belongs to another axis is
   moved the same way.
2. Rewrite the leads that confirmed findings say they settle, in the lead's
   own file: `closed: settled by F-…`, or for a part `open: <part> settled
   by F-…; remains <what>, <who>`. A refuted finding settles nothing.
3. List the axes that received leads after they ran: each needs a lead pass
   (`finding-format`, Leads).

## End report

Per axis: confirmed, refuted, unverified, ratings changed, text corrected,
leads reopened, moved, or closed as settled; then the questions added, the
citations added between findings with one cause, and the axes that need a
lead pass. Continue with those lead passes, or with `audit-report`.
