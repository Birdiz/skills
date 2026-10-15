# Deliverables

## Peer report

Complete, for a technical reader who will act on it or challenge it.

1. **Summary**: confirmed findings by severity and axis; the number of
   fixes, by executor; quick wins; the first three fixes of the plan's
   order, one sentence each, and any high-severity fix waiting for a
   decision, with the decision.
2. **Scope and coverage**: each axis's coverage in one common table (area,
   status, note); gaps as visible as findings.
3. **Remediation plan**: the plan's order table, then each fix: title, ID,
   its findings, why together, change, check, what it waits for. A finding
   is counted in its axis; a fix, once.
4. **Findings**, every confirmed one, by axis, severity, effort: title, ID,
   its fix, rating line (severity, confidence, effort, evidence regime),
   evidence condensed to its key pointers (the findings file holds the
   rest), technical explanation, remediation, what verification
   established.
5. **Not verified**, kept apart from confirmed ones: reason, and who can settle
   it.
6. **Accepted**: owner's decision and date; outside quick wins.
7. **Open leads and questions**: what each would change; answers received.
   Controls and facts declared by the owner and not observed (leads closed
   as declared, coverage lines `declared, not observed`), each with its
   question: the audit relies on them without having seen them.
   Questions by ID (by axis and order when they have none), each once,
   those asked and unanswered apart from those never asked; an answer that
   would move several ratings (an obligation, a volume, a decision not yet
   taken) says so once, with the effect on counts. Leads and questions
   opened by the last lead pass, or after it, are named as waiting for the
   next run.
8. **Refuted**: one line each (ID, title, why).
9. **Method and limits**: mapping method, dependency source, running target,
   standing unknowns, cosmetic discrepancies.

## Plain-language summary

For a decision maker who reads no code. Two pages at most.

1. **What was looked at, and what was not**, unaudited axes named plainly.
2. **The overall picture**, three to five sentences.
3. **Quick wins**: the quick-win fixes, each with an everyday title, why it
   matters (from its findings' plain-language explanations), what fixing
   involves, who usually does it.
4. **To go further**: the other fixes by theme, a sentence or two each;
   those waiting for a decision say which.
5. **What we need from you**: the owner's questions, without jargon.

Open fixes only; accepted findings as one line ("N points were kept as they
are, by decision"). IDs only in a closing table, fixes with their findings.
A `sensitive` fix is told by its consequence alone: no file, entry point,
parameter, host or method. A severity label comes with its meaning.

## Remediation prompts

One self-contained prompt per `promptable` quick-win fix, covering all its
findings; the other `promptable` fixes if the auditor asked, in the plan's
order.

- `executable`, to a coding agent in the repository: stack and
  repository-relative files, the target behaviour, constraints (what stays,
  conventions), the check of each finding as a test or command.
- `vendor-brief`, to a developer: what to change, why in one sentence, how to
  check.
- `both`: both forms.

Prompts leave the confidential perimeter, so they describe the target state
only: no exploitation path, payload, secret, personal data, or production host
or URL. Quick-win fixes that are not `promptable` close the file under "To
do by hand", with their executor and how to check.
