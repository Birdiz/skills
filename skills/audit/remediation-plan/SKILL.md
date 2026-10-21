---
name: remediation-plan
description: Group the confirmed findings of an audit into fixes (one piece of work each, resolving one or more findings), ordered, with who does each and what it waits for. Use after the last verify-findings and before audit-report, or when asked for a remediation plan of an audit workspace.
---

# remediation-plan

Version: 0.19.0 (audit skills, see CHANGELOG)

Turn findings into work. A **fix** is what one person does in one go (a pull
request, a session in a console, a decision): it resolves one or more
findings. Input: `00-engagement.md`, `01-codebase-map.md`, `findings/*.md`.
Output: `<workspace>/02-remediation-plan.md`. Bound by
[rules of engagement](../finding-format/rules-of-engagement.md).

The plan adds no finding and changes none: it reads what verification left.
Remediations stay owned by their findings; the plan joins them.

## Before starting

1. Read the engagement file, `finding-format`, and in every findings file
   what planning needs: each finding's YAML, technical explanation,
   remediation, verification note and auditor answer, and the questions
   with their answers.
2. Take every finding `confirmed` with `resolution: open`. One that is
   `unverified` waits for `verify-findings`; `refuted`, `accepted` and
   `fixed` ones have nothing to plan.
3. An existing plan is updated, never rewritten from nothing (Updating).
   The plan is stale, and this step runs again, when a finding enters or
   leaves the set above, or when a finding's verification note or auditor
   answer is dated after the plan's `generated`.

## Grouping

Each finding goes into exactly one fix. Findings share a fix when:

- **one change** resolves them all: their technical explanations cite one
  cause, or their remediations describe the same change at the same
  locations (`grouping: one-change`);
- **the same files**, changed by the same executor in one go, each by its
  own change in the same place (a block, a template, a service) or with
  remediations that cite each other (`grouping: same-files`), provided the
  findings are all sensitive or all not, and the group neither waits for
  more nor costs more effort than its most severe finding alone would (the
  group's effort is judged whole and stated).

Anything else (the same mechanism in other files, a cause shared in part,
the same console, a fix that needs another first) stays in separate fixes,
linked by `waits_for` or named in the reason. A fix with one finding is
`grouping: single`. Each fix states its grouping, with a pointer: the
sentence that names the cause, or the place both remediations change; a
single fix names the related findings kept apart, and why.

A finding is never split across fixes. A remediation offering options keeps
them: a group may name the option its findings share, and the fix waits for
nothing unless the choice is the owner's (below).

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

**Grouping.** The cause both findings name (F-A11Y-008, technical
explanation; F-PERF-008, verification note).

**Change.** The target state, from the findings' remediations, in steps
when several executors take part.

**Check.** Each finding's check, by ID.
````

- **Executor**: who does the main change. `code` for a change in the
  repository, its content included (a template, a colour); `operations` for
  a host, a console, the forge or the cloud; `owner` when the fix is itself
  a decision, a legal or organisational text, or a document only the owner
  can give. Steps for another executor are named in the change.
- **Waits for**: a fix to do first, or a decision the owner has not taken:
  a question unanswered, answered "not decided", or deferred to someone
  else (counsel), by ID (`<axis> question <n>` when it has none), or a
  decision the remediation places before the work, named. A choice made
  while doing the fix waits for nothing; a fix that is the decision has
  executor `owner` and waits for nothing. A fix waiting for a decision is
  still planned, so the decision shows as the blocker; a remediation with
  a first step that waits for nothing says so in the change.
- **Change** describes the target state, never the attack: tickets and
  prompts are drawn from it. **Check** keeps every case each finding
  showed, described as behaviour to test (a redirect to another host, in
  any of the forms the finding found), so a test written from it fails
  before the fix. A step of the change that waits for nothing has its own
  check, so the work it allows can be closed. Tickets restate the check
  outside the workspace: it names its cases, or points to where they are
  listed.
- **`locations`**: where the change lands, not the evidence.
- **Quick win**: an open fix of severity medium or above, effort S, waiting
  for nothing. Deliverables count quick wins this way.

## Order

Three tiers: fixes waiting for nothing, then fixes waiting only for other
fixes (each after those it waits for), then fixes waiting for a decision,
with the decision. Within a tier: severity, then effort, then ID. The order
is the `## Order` table. A first plan numbers its fixes in that order;
later fixes take the next free ID, so IDs stop following the order.

## Updating

`R-` IDs are never reused or renumbered: tickets point at them. On a
later run, a fix keeps its ID while any of its findings is still in it; a
finding newly confirmed joins a fix by the same rules, or opens a new one;
a finding fixed, accepted or refuted leaves its fix. A fix left empty
becomes `done` when its findings were fixed, `dropped` otherwise, and stays
in the file. Each change of membership after the first plan is one dated
line under the fix.

## Checking

Every script that computes what the plan states is kept in
`tool-output/plan/`; the header's `tools` are those whose output the plan
relies on. A script there, run with `bash`, checks that every confirmed
open finding is in exactly one open fix, that every ID cited exists (a
finding with the status given, a question waited for still undecided), that
`severity`, `promptable` and `sensitive` follow from the findings, and that
nothing comes before what it waits for. The validator (`finding-format`,
Validator), run with `--require verification --require plan`, checks all
of it but the questions' answers, which the script reads itself; without
Python 3, the script checks all of it. Its output is kept beside it.

## End report

Fixes by executor and severity, quick wins, fixes waiting for a decision
(with the decision), groups formed and why in one line each, discrepancies;
then continue with `audit-report`.
