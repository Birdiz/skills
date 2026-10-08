---
name: verify-findings
description: Try to refute every unverified audit finding from a context that did not produce it, and set each one to confirmed, refuted, or left unverified with a reason. Use after the axes of an audit have run, before any report, or when findings files contain unverified findings.
---

# verify-findings

Version: 0.4.0 (audit skills, see CHANGELOG)

The only step allowed to set a finding's `status` to `confirmed` or
`refuted`. Everything downstream (quick wins, reports, tickets) stands on its
result.

Input: `00-engagement.md`, `01-codebase-map.md`, `findings/*.md`, the working
copy. Output: the same findings files, updated in place.

## Independence

The verifier must not be the context that wrote the findings. Reason: an
agent re-reading its own reasoning finds it convincing; that is not a check.

- **Sub-agents available**: run the verification in one. Give it file paths
  only (workspace, working copy, this skill), never the conversation or a
  summary of what the axis thought.
- **No sub-agents**: if this session wrote any of the findings, stop and tell
  the auditor to open a new session and invoke `verify-findings` there. The
  workspace holds everything that session needs. This is a blocker, not an
  optional accelerator.

Record which one in each verification note (`by: sub-agent | new session`).

## Stance

Try to refute, not to confirm. For each finding, the question is "what would
make this wrong?", and the finding is confirmed only when every answer has
been checked and failed.

## Per finding

Work through every finding with `status: unverified`, in severity order.

1. **Reproduce the evidence.** Open every location; check the line says what
   the finding claims, at the audited commit. Rerun the commands in the
   evidence when the rules allow it (analysis tools, passive requests). A
   pointer that does not match is enough to stop and refute or correct.
2. **Look for the missing control elsewhere.** Framework defaults, a listener,
   middleware or config applied globally, a check upstream of the entry point,
   infrastructure in the repository. Read the dependency code `recon` made
   available rather than recalling framework behaviour.
3. **Check reachability and preconditions.** Who can reach it, through which
   entry point, under which conditions. A weakness behind a check the finding
   did not mention may be real but lower.
4. **Check the rating.** Severity against the axis grid, with the finding's
   own stated adjustment; confidence; `sensitive` and `promptable` against
   `finding-format`; references against their source.
5. **Decide.**

| Result | When |
|---|---|
| `confirmed` | Evidence reproduced, no control found, reachability as stated |
| `refuted` | Evidence does not hold, or a control fully prevents the consequence |
| `unverified` (stays) | It cannot be checked with the engagement's capabilities (a dynamic finding with the target down, a production setting), or only the auditor or owner can settle it |

A finding that holds but is rated wrong is `confirmed` with the corrected
rating. Never leave a wrong severity in place because the weakness is real.

## Writing the result

**Correct in place.** When verification proves part of the finding wrong (a
pointer, a claim in the evidence, a scenario, a remediation that would not
work, a reference that does not say what the finding claims), rewrite that
passage in the finding itself and quote the replaced text in the note. Reason:
reports are generated from these files; a known error left in place reaches
the reader. Correct only what was proven wrong; do not restyle the rest.

Add a `**Verification.**` paragraph after `**Remediation.**`, and two YAML
keys:

```yaml
status: confirmed
verification: {by: sub-agent, on: 2026-10-08}
```

```markdown
**Verification.** Reproduced: src/Security/UserChecker.php:20-25 and the
listener priorities (vendor/...:56, vendor/...:94). No global control found.
Severity kept at medium.
```

- Refuted: say what makes it wrong, with pointers. The finding stays in the
  file so the same false positive is not rediscovered.
- Rating changed: give the old and new values and the reason, change the
  YAML, and change every sentence of the finding that states the old rating.
  A rating change without a stated reason is not allowed.
- Text corrected: quote the old passage and say what proved it wrong.
- Left unverified: say what is missing and who can settle it, and add the
  question to `## Questions for the auditor`.

## Leads

Do not re-investigate open leads; they belong to their axis. Do spot-check
the ones marked `closed`: pick the closures with the weakest stated reason
and check them. A wrong closure becomes a lead again, with `open:` and the
reason, for the axis to pick up.

## Rules

**No new findings.** Something new noticed during verification is written
as a lead in the owning axis file. Reason: a finding the verifier wrote
would have no verifier.

**Same limits as the axes.** Passive unless the engagement records active
testing, and then only on the listed hosts. Passive means no guessed URLs or
identifiers either: request only what a page links to or what the auditor
provided. Never execute the audited project. Never quote a secret.

**Every finding gets a note**, including confirmed ones. A bare status change
cannot be audited later.

## End report

Counts per axis: confirmed, refuted, still unverified, ratings changed, and
closed leads reopened. Then the questions added for the auditor.
