---
name: verify-findings
description: Try to refute every unverified audit finding from a context that did not produce it, and set each one to confirmed, refuted, or left unverified with a reason. Use after the axes of an audit have run, before any report, or when findings files contain unverified findings.
---

# verify-findings

Version: 0.8.0 (audit skills, see CHANGELOG)

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
has been checked and failed. Take every `unverified` finding, by severity.

1. **Reproduce.** Open each location at the audited commit; rerun the evidence
   commands the rules allow. A pointer that does not match settles it: refute
   or correct.
2. **Find the control elsewhere**: framework defaults, global listeners,
   middleware or config, an upstream check, infrastructure in the repository,
   read in the dependency code `recon` provided.
3. **Reachability**: who, through which entry point, under which conditions;
   an unmentioned check may leave it real but lower.
   For `code-quality` and `architecture`: the code is on the flow the finding
   names, and the claimed cost is shown (history, diverged copies, a failure
   path); a preference is refuted.
4. **Rating**: severity against the axis grid and the stated adjustment;
   confidence; `sensitive` and `promptable` against `finding-format`;
   references against their source.
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
these files. The rest stays as written.

- Refuted: what makes it wrong, with pointers.
- Rating changed: old value, new value, reason; the YAML and every sentence
  stating the old value updated.
- Text corrected: the old passage and what proved it wrong.
- Unverified: what is missing, who can settle it, and an entry in `##
  Questions for the auditor`.

## Revision mode

Discrepancies listed by `audit-report` or the auditor in verified findings
(text against YAML, unapplied corrections, unopenable citations) are applied
in place under the same rules, `confirmed` findings included. Re-check only
what the correction touches; add one line to the note saying what was revised
and when.

## Leads

Open leads are left to their axis, uninvestigated. Spot-check the `closed`
ones with the weakest reasons; a wrong closure goes back to `open:` with the
reason. Anything new becomes a lead in the owning axis file: a finding written
by the verifier would have no verifier.

## End report

Per axis: confirmed, refuted, unverified, ratings changed, text corrected,
leads reopened; then the questions added. Continue with `audit-report`.
