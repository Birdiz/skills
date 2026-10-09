# Deliverables

## Peer report

Complete, for a technical reader who will act on it or challenge it.

1. **Summary**: confirmed findings by severity and axis; quick wins; the two or
   three that matter most, one sentence each.
2. **Scope and coverage**: each axis's coverage table; gaps as visible as
   findings.
3. **Findings**, every confirmed one, by axis, severity, effort: title, ID,
   rating line (severity, confidence, effort, evidence regime), evidence,
   technical explanation, remediation, what verification established.
4. **Not verified**, kept apart from confirmed ones: reason, and who can settle
   it.
5. **Accepted**: owner's decision and date; outside quick wins.
6. **Open leads and questions**: what each would change; answers received.
7. **Refuted**: one line each (ID, title, why).
8. **Method and limits**: mapping method, dependency source, running target,
   standing unknowns, cosmetic discrepancies.

## Plain-language summary

For a decision maker who reads no code. Two pages at most.

1. **What was looked at, and what was not**, unaudited axes named plainly.
2. **The overall picture**, three to five sentences.
3. **Quick wins**: everyday title, why it matters (from the plain-language
   explanation), what fixing involves, who usually does it.
4. **To go further**: other confirmed findings by theme, a sentence or two
   each.
5. **What we need from you**: the owner's questions, without jargon.

Open confirmed findings only; accepted ones as one line ("N points were kept
as they are, by decision"). IDs only in a closing table. A `sensitive` finding
is told by its consequence alone: no file, entry point, parameter, host or
method. A severity label comes with its meaning.

## Remediation prompts

One self-contained prompt per confirmed `promptable` quick win; the other
confirmed `promptable` findings if the auditor asked.

- `executable`, to a coding agent in the repository: stack and
  repository-relative files, the target behaviour, constraints (what stays,
  conventions), the remediation's check as a test or command.
- `vendor-brief`, to a developer: what to change, why in one sentence, how to
  check.
- `both`: both forms.

Prompts leave the confidential perimeter, so they describe the target state
only: no exploitation path, payload, secret, personal data, or production host
or URL. Quick wins that are not `promptable` close the file under "To do by
hand", with who does it and how to check.
