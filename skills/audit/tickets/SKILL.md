---
name: tickets
description: Turn the fixes of an audit's remediation plan into tickets, one per fix, in the target's issue tracker when the engagement allows it, as local files otherwise. Use after audit-report, or when asked for the tickets of an audit workspace.
---

# tickets

Version: 0.22.0 (audit skills, see CHANGELOG)

One **ticket** per open fix of the plan: the work handed to whoever does it,
where they track work. Input: `00-engagement.md`, `02-remediation-plan.md`,
`findings/*.md`, `reports/`, and the target's tracker when the engagement
names one. Output: `<workspace>/tickets/`, and new issues in that tracker.
Bound by [rules of engagement](../finding-format/rules-of-engagement.md).

A ticket is drawn from its fix and adds nothing: no finding, no grouping, no
remediation of its own; what it takes from elsewhere is only what the plan
points to (Pointers). One fix, one ticket, never split. Once created in a
tracker it belongs to the team: this step never edits, comments on,
relabels, closes or deletes it, beyond the dependency links made right
after it (Creating, step 4).

## Before starting

1. Read the engagement file and its `## Tickets`, `finding-format`, the
   plan, the conventions files it names, and in each fix's findings what a
   ticket draws on: evidence (to judge checks), plain-language
   explanation, remediation, `sensitive`. The conventions are read as they
   stand on the tracker's default branch, through its API (the team's
   current ones), or in the audited working copy when the destination is
   local; which one, with its commit, goes under the index's `## Notes`.
2. **Verification present and plan current**, as `audit-report` requires
   them (Before writing, step 2); otherwise the step it names first. The
   validator (`finding-format`, Validator), run with `--require
   verification --require plan`, checks both; its output is kept with this
   run's scripts and `finding-format@<version>` listed in `tools`. Apart
   from what `--require` makes errors, which send to their step, its
   errors hold nothing of themselves: the report sorts them
   (`audit-report`, Before writing, step 5), and a blocking one reaches a
   fix through the DRAFT list. The report's run folder is the one its
   provenance names (`audit-report`, Before writing, step 2). An error
   missing from the validator output kept there (a newer validator, or a
   report that kept none) is unsorted: `audit-report` first. A plan
   written by an older version of `remediation-plan` is current unless it
   is stale by that skill's rule.
   **Report current**: the hashes in the `inputs.sha256` of the report's
   run folder match the plan and findings files now; no report, no hashes
   (a report built before they were kept), or one differing:
   `audit-report` first.

   `audit-report` first holds creation only: the run still prepares the
   tickets, the index and, for a tracker, the question, from the report as
   it stands; it writes `allowed: pending` with the reason and asks
   nothing; the next run, on a current report, computes again and asks.
3. **Ready fixes**: each `open` fix of the plan, unless:
   - a blocking item of the report's DRAFT list (the peer report's, or
     any deliverable's: they carry the same list) holds it, by its
     `Holds:` line; in a report without that line, by naming the fix or
     one of its findings as something it could change (an ID cited only
     for comparison holds nothing). The whole fix waits, with the item's
     number;
   - it waits for a fix that is not ready (`waits: R-NNN`);
   - its check does not hold (Pointers): `waits: plan check`, for
     `remediation-plan`.

   A report without DRAFT holds no fix.

   **Done since the audit**: when the tracker's default branch has moved
   past the audited commit, read its commits after that commit, and the
   issues and pull requests closed since the audit began whose merge
   commit is not the audited commit or one before it, through the
   tracker's API, never fetched into the audited working copy.
   Candidates are the commits touching the fix's `locations` and the
   issues or pull requests naming its fix or finding IDs, each judged
   from its diff (an issue by the merged pull requests its timeline says
   close or reference it): a shared file alone shows nothing, a directory
   location included.
   A fix not yet sent whose change shows there, whole, in part or going
   further, is `possibly done after <commit>`, with the commit or issue
   and, for a part, what it covers in one line; `verify-findings` decides.
   A ready one is `local: possibly done after <commit>`, listed in the
   question and created only when the answer names it ("all" covers the
   tickets listed to create); a waiting or struck one keeps its state,
   that line beside it. All are named in the end report for
   `verify-findings` on a later commit. A fix waiting for a ready one
   stays ready, blocked by it by title, linked only when both are
   created. The agent reads each diff with secret values masked, and
   writes its judgment into the script as data; the script prints, for
   each candidate, its commit or issue, its files and that judgment,
   never a patch or a body, and keeps none: they may hold a secret value.
   Patches or bodies an earlier run kept are named in the end report, for
   the auditor to remove.
4. An existing `tickets/index.md` is updated, never rewritten from nothing
   (Later runs).

Readiness is computed by a script in `tool-output/tickets/` (a later
run in its own folder, as the rules of engagement name it), its output
kept beside it. This run's scripts below all go in the same folder.

## Destination

From `## Tickets`:

- `destination: tracker`, with its permission recorded: ready fixes go to
  the tracker, except a `sensitive` one when `visibility` is not
  `restricted`, which stays local. `restricted` means only people the
  owner grants can read the tracker (a private repository, a project with
  permissions), as its API reports it.
- `destination: local`, or no `## Tickets` (an engagement older than this
  step): every ticket is a local file, for the auditor to hand over. A
  tracker settled later is a kickoff amendment.

Before creating, read the tracker's visibility again through its API; one
that no longer matches the record stops every creation, and goes back to
`audit-kickoff`.

## A ticket

All of it in the engagement's `language`, unless the conventions name
another: headings, closing line, the severity word as the report writes it.

When the engagement names conventions files (an agent's guide to the
tracker, a contributing guide, issue templates), they win aspect by aspect
over the form below: sections, where dependencies go and how they link,
labels among those `labels:` maps. Two never follow them: this step creates
no label or milestone, and it never splits a fix (a fix the conventions
would split, by size or subject, is noted in the index for the auditor).
Otherwise:

```markdown
# <the fix's title>

## Why
<what goes wrong, for whom>

## Change
<the fix's Change: the target state, in steps when it has several; the
locations in the repository where it lands>

## Acceptance criteria
- [ ] <each finding's check, from the fix's Check, as behaviour to test>

## Blocked by
<a fix waited for: its ticket, as the tracker links it, or its title; a
decision: the question or decision in words; or "nothing">

## Size
<S: hours | M: days | L: weeks>

From the audit of <target> at <short commit> (plan of <generated>): fix
R-001 (F-A11Y-008, F-PERF-008), severity medium.
```

The closing line is always there, whatever the conventions: it ties the
ticket to its fix, and a search for the fix ID finds it.

A ticket leaves the workspace, so it carries the target state and what to
test, never how the problem is exploited: no evidence, exploitation path,
payload, request that triggers it, secret (by variable name only), personal
data, production host or URL, workspace path, or lead or question ID.

- **Why** says what goes wrong and for whom, from the findings'
  plain-language explanations, never who could cause it, from where, by
  what means, nor what limits it today. A sensitive fix's Why is its
  consequence alone, as the summary tells it (the plain-language
  explanation's consequence when there is no summary). The plain-language
  explanations were written for the confidential report: reread each
  sentence against this rule before using it.
- **Acceptance criteria** keep every case the fix's Check holds
  (every page, every form, every row) and name the kinds of input to test,
  not a literal one ("a destination on another host, in every form the
  filter accepts", not the string).
- A sensitive fix in a restricted tracker keeps its files and checks under
  the same rule. Its local file opens with
  `<!-- sensitive: access-restricted tracker only -->`; the body sent opens
  with this line, translated into the ticket's language, so it reads as
  such if the tracker opens: "This ticket stays in an access-restricted
  tracker: do not copy it elsewhere."

## Pointers

The plan may point into the workspace: a script or tool output that holds a
check, a file that lists the cases, a question by ID, a lead. The ticket
replaces each with what it points to, and only that: the cases the script
checks, the rows the file lists, the owner's answer or the open decision in
words. A lead ID is dropped. Each replacement is one line under the index's
`## Notes`.

A check holds when its restatement keeps every case, a test written
from it fails before the fix, and every part of the Change (each step,
each place it lands) is tested by one of its criteria. One that would not
(it loses a case, the finding's evidence shows the code already does what
it asks, or a part of the Change has no criterion) holds its fix, `waits:
plan check`, with what is wrong in one line, for `remediation-plan`; the
other fixes go on.

## Creating

1. Write each ready fix's ticket to `tickets/R-NNN.md`, those for the
   tracker included.
2. A script in this run's folder checks every ticket: title and size
   as in the plan, closing line present, no workspace path, lead or
   question ID, URL (`scheme://`), host name of the target, e-mail address
   or `<redacted>`, anywhere in the file. It is run once on tickets broken
   on purpose, so a check that reads nothing fails. Its output is kept
   beside it.
3. When tickets go to the tracker, the index first lists them all: those
   to create (fix, title, labels, what each is blocked by, the dependency
   links the conventions make), then those kept local, waiting, possibly
   done or struck before (Later runs), each with its reason. Then **ask
   once**, through the structured question tool when there is one: the
   counts (tickets and dependency links, and the fixes struck before and
   not offered, those now waiting counted apart), the possibly done among
   those to create, the index's path, and three answers: all, only the
   fixes the auditor names (a fix struck before included), or none. The
   question is written under the index's `## Notes` first, and asked as
   written: a run that cannot reach the auditor (a sub-agent) stops there
   with `allowed: pending: question prepared, not asked`, and whoever
   resumes it asks that text. Only a clear yes creates. The answer goes in
   `allowed:`, verbatim, with its date, and below the question in Notes
   the fixes it covers, one list, which the creation script reads; a fix
   left out becomes `local: struck by the auditor (<date>)`, its ticket
   kept as `tickets/R-NNN.struck.md`. Without a yes, the files stay
   local. When nothing goes to the tracker, nothing is asked, and
   `allowed: n/a`.
4. Create in the plan's order, so a ticket waited for exists before the
   one waiting for it. Before each, read its index row, then search the
   tracker for the fix ID in the closing line (an empty search is printed
   as such): a ticket recorded or found is not created again. The body
   sent is the local file without its marker and title line, a sensitive
   one opening with its restricted-tracker line, a ticket waited for named
   by its tracker reference (`#n`). Each creation is
   scripted in `run-create.sh` in this run's folder, for the fixes the
   answer covers as Notes lists them, through the tracker's
   CLI or MCP server, labels set at creation, the body sent kept as
   `tickets/R-NNN.sent.md`, and recorded in the index as soon as it
   succeeds, so a run stopped midway resumes. A dependency link the
   conventions make natively, listed in the index the yes answered, is
   made right after the waiting ticket, read back, and noted under the
   index's `## Notes`.

## Index

`tickets/index.md`, in the engagement's `language`, keys and states in
English:

```markdown
# Tickets
plan: 02-remediation-plan.md, generated <YYYY-MM-DD>
skill: tickets@<version>
tools: [<name@version>]
destination: <tracker: kind, project, visibility checked YYYY-MM-DD | local>
allowed: <"the auditor's answer", verbatim (YYYY-MM-DD), question in Notes | pending: <reason> | n/a>

| Fix | Ticket | Labels | Sent | State |
|---|---|---|---|---|
| R-001 | <tracker URL> | ready-for-agent, plateforme | 2026-10-27, tickets@0.22.0 | sent |
| R-010 | tickets/R-010.md | ready-for-human, plateforme | — | local: sensitive, tracker public |
| R-013 | — | — | — | waits: report item 3 |

## Notes
```

Rows in the plan's order. Labels live here and in the tracker, never in a
ticket's body; in a local run they are what the mapping gives, for the
auditor. A label the mapping gives but the tracker lacks is left out,
and noted. A sent ticket's labels are those set at creation; the team
relabelling it later is one line under `## Notes`. `Sent`: the date and
the skill version that sent it. `tools`: those whose output the index
relies on. An update keeps the `skill` and `tools` lines it replaces
under `## Notes`, with their run's date, so `audit-kickoff` can copy
every run's versions. States:
`ready: awaiting the auditor's yes` until the question is answered;
`sent`; `local` with its reason (destination, sensitive, struck by the
auditor (<date>), possibly done after a commit); `waits` with every
reason (report item, fix, plan check); and on later runs, for a sent
ticket, `changed since sent`, `fix done`, `fix dropped` or `closed in
tracker`. Reasons combine in one cell, separated by `;` (`waits: report
item 7; struck by the auditor (2026-10-24)`).
`## Notes`: the conventions read, the pointers replaced, the fixes the
conventions would split, the question and the fixes its answer covers,
each run's creations and links, the earlier runs' `skill` and `tools`,
any choice the skill left open.

## Later runs

A fix never gets a second ticket. A fix is struck when an answer
recorded in an index struck it, or when its row says so; a later run
that asked nothing and wrote another state over it unstrikes nothing.
First, a struck fix without `tickets/R-NNN.struck.md` (struck before
that file was kept) gets its `tickets/R-NNN.md` copied there, and an
`R-NNN.sent.md` an earlier run kept in `tool-output/tickets/` is moved
to `tickets/`. Then the local files are regenerated from the plan; the
file of a fix neither ready nor sent is moved into this run's folder,
under `removed/`, wherever an earlier run left it under `tickets/`,
except `R-NNN.struck.md`, kept while its fix is open, and the
`superseded-*` folders, left as they are. A sent ticket keeps its
row, link and `tickets/R-NNN.sent.md`; a hold on its fix now (report
item, fix, plan check) is one line beside its state, for the auditor to
tell the team. Its state, from the plan and the tracker:

- `changed since sent`: its regenerated body, prepared as sent, differs
  from `R-NNN.sent.md` by something drawn from the plan, the findings or
  the report, with what changed in one line. A difference from this
  skill's own form alone (the marker, the restricted-tracker line, the
  closing line's wording and plan date, how a ticket waited for is named)
  is no change: one line under `## Notes`.
- `fix done` or `fix dropped`: the plan says so.
- `closed in tracker`: the issue is closed while its fix is still open in
  the plan, with how the tracker says it was closed (completed or not
  planned) and what closed it: the closing event's commit, else the
  merged pull request that references the issue, or `none given`;
  named in the end report for `verify-findings` on a later commit. It
  replaces `changed since sent`, whose line is still written in the same
  cell.

The auditor handles these in the tracker. A struck fix stays struck while
its regenerated ticket matches `tickets/R-NNN.struck.md`, form alone
aside, whatever else its row says (waiting, possibly done, no longer
waiting): it is counted in the question, and created only when the
answer names it. One that differs, a new fix, one no longer waiting that
was never struck, and one kept local because the destination was local
before a tracker was settled go through Creating.

## End report

Tickets created, with their links, and the dependency links made; kept
local, and why, struck fixes not offered again counted; possibly done
since the audit and closed in the tracker, for `verify-findings` on a
later commit; waiting, and for what (report item, fix, plan check, routed
to its step); sent tickets needing the auditor (changed, done, dropped);
creation held for `audit-report`, with the reason; the labels set;
patches or bodies an earlier run kept; and that nothing else was
written in the tracker.
