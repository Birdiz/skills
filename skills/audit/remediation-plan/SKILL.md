---
name: remediation-plan
description: Group the confirmed findings of an audit into fixes (one piece of work each, resolving one or more findings), ordered, with who does each and what it waits for. Use after the last verify-findings and before audit-report, or when asked for a remediation plan of an audit workspace.
---

# remediation-plan

Version: 0.15.0 (audit skills, see CHANGELOG)

Turn findings into work. A **fix** is what one person does in one go (a pull
request, a session in a console, a decision): it resolves one or more
findings. Input: `00-engagement.md`, `01-codebase-map.md`, `findings/*.md`.
Output: `<workspace>/02-remediation-plan.md`. Bound by
[rules of engagement](../finding-format/rules-of-engagement.md).

The plan adds no finding and changes none: it reads what verification left.
Remediations stay owned by their findings; the plan joins them.

## Before starting

1. Read the engagement file, `finding-format`, every findings file.
2. Take every finding `confirmed` with `resolution: open`. One that is
   `unverified` waits for `verify-findings`; `refuted`, `accepted` and
   `fixed` ones have nothing to plan.
3. An existing plan is updated, never rewritten from nothing (Updating).

## Grouping

Each finding goes into exactly one fix. Findings share a fix when:

- **one change** resolves them all: their technical explanations cite one
  cause, or their remediations describe the same change at the same
  locations (`grouping: one-change`);
- **the same files**, changed by the same executor in one go, each by its
  own change (`grouping: same-files`), provided the group neither waits for
  more nor costs more effort than its most severe finding alone would.

Anything else (the same mechanism in other files, a fix that needs another
first) stays in separate fixes, linked by `waits_for` or named in the
reason. A fix with one finding is `grouping: single`. Each group states why,
with a pointer: the sentence that names the cause, or the files both
remediations change.

Two remediations that contradict each other are not merged: their findings
stay in separate fixes, and the conflict goes under `## Discrepancies`, for
`verify-findings` in revision mode. The plan never rewrites a remediation.

## The plan

```markdown
# Remediation plan
commit: <sha>
skill: remediation-plan@<version>
tools: [<name@version>]
findings: <N confirmed open, from findings/*.md read on YYYY-MM-DD>
generated: <YYYY-MM-DD>

## Order
| # | Fix | Title | Severity | Effort | Executor | Waits for | Quick win |
|---|---|---|---|---|---|---|---|

## Fixes
## Discrepancies
```

Each fix, in the engagement's `language`, keys and values in English:

````markdown
### R-001 Stop the animations after a few cycles

```yaml
id: R-001
findings: [F-A11Y-008, F-PERF-008]
grouping: one-change      # single | one-change | same-files
status: open              # open | done | dropped
severity: medium          # the highest of its findings
effort: S                 # S | M | L, the whole fix
executor: code            # code | operations | owner
promptable: true          # every finding promptable
sensitive: false          # any finding sensitive
waits_for: []             # R-… to do first, Q-… or a decision named
locations:
  - assets/styles/app.css:120
```

**Why together.** The cause both findings name (F-A11Y-008, technical
explanation; F-PERF-008, verification note).

**Change.** The target state, from the findings' remediations.

**Check.** Each finding's check, by ID.
````

- **Executor**: `code` for a change in the repository, `operations` for a
  host, a console, the forge or the cloud, `owner` for a decision, a text or
  a document only the owner can give.
- **Waits for**: a fix to do first, or a decision the owner has not taken
  (an unanswered or undecided question, by ID). A fix waiting for a
  decision is still planned, so the decision shows as the blocker.
- **Change** describes the target state, never the attack: tickets and
  prompts are drawn from it.
- **Quick win**, derived: open, severity medium or above, effort S, nothing
  to wait for.

## Order

Fixes waiting for nothing come first, then by severity, then by effort,
quick wins first among equals; a fix always comes after those it waits
for. Fixes waiting for a decision close the order, with the decision. The
order is the `## Order` table; IDs never encode it.

## Updating

`R-` IDs are never reused or renumbered: tickets will point at them. On a
later run, a fix keeps its ID while any of its findings is still in it; a
finding newly confirmed joins a fix by the same rules, or opens a new one;
a finding fixed, accepted or refuted leaves its fix. A fix left empty
becomes `done` when its findings were fixed, `dropped` otherwise, and stays
in the file. Each change of membership is one dated line under the fix.

## Checking

A script in `tool-output/plan/`, run with `bash`, checks that every
confirmed open finding is in exactly one open fix, that every ID cited
exists with the status given, that `severity`, `promptable` and `sensitive`
follow from the findings, and that nothing comes before what it waits for.
Its output is kept beside it.

## End report

Fixes by executor and severity, quick wins, fixes waiting for a decision
(with the decision), groups formed and why in one line each, discrepancies;
then continue with `audit-report`.
