---
name: tickets
description: Turn the fixes of an audit's remediation plan into tickets, one per fix, in the target's issue tracker when the engagement allows it, as local files otherwise. Use after audit-report, or when asked for the tickets of an audit workspace.
---

# tickets

Version: 0.19.0 (audit skills, see CHANGELOG)

One **ticket** per open fix of the plan: the work handed to whoever does it,
where they track work. Input: `00-engagement.md`, `02-remediation-plan.md`,
`findings/*.md`, `reports/`, and the target's tracker when the engagement
names one. Output: `<workspace>/tickets/`, and new issues in that tracker.
Bound by [rules of engagement](../finding-format/rules-of-engagement.md).

A ticket is drawn from its fix and adds nothing: no finding, no grouping, no
remediation of its own; what it takes from elsewhere is only what the plan
points to (Pointers). One fix, one ticket, never split. Once created in a
tracker it belongs to the team: this step never edits, comments on,
relabels, closes or deletes it.

## Before starting

1. Read the engagement file and its `## Tickets`, `finding-format`, the
   plan, the conventions files it names, and in each fix's findings what a
   ticket draws on: evidence (to judge checks), plain-language
   explanation, remediation, `sensitive`.
2. **Verification present and plan current**, as `audit-report` requires
   them (Before writing, step 2); otherwise the step it names first. A plan
   written by an older version of `remediation-plan` is current unless it
   is stale by that skill's rule. No report yet: `audit-report` first.
3. **Ready fixes**: each `open` fix of the plan, unless:
   - a blocking item of the report's DRAFT list (the peer report's, or
     any deliverable's: they carry the same list) names the fix or one of
     its findings as something it could change; an ID cited only for
     comparison holds nothing, and an item naming no finding or fix holds
     no fix. The whole fix waits, with the item's number;
   - it waits for a fix that is not ready (`waits: R-NNN`);
   - its check does not hold (Pointers): `waits: plan check`, for
     `remediation-plan`.

   A report without DRAFT holds no fix.
4. An existing `tickets/index.md` is updated, never rewritten from nothing
   (Later runs).

Readiness is computed by a script in `tool-output/tickets/`, its output
kept beside it.

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
  consequence alone, as the summary tells it. The plain-language
  explanations were written for the confidential report: reread each
  sentence against this rule before using it.
- **Acceptance criteria** keep every case each finding's check holds
  (every page, every form, every row) and name the kinds of input to test,
  not a literal one ("a destination on another host, in every form the
  filter accepts", not the string).
- A sensitive fix in a restricted tracker keeps its files and checks under
  the same rule. Its local file opens with
  `<!-- sensitive: access-restricted tracker only -->`.

## Pointers

The plan may point into the workspace: a script or tool output that holds a
check, a file that lists the cases, a question by ID, a lead. The ticket
replaces each with what it points to, and only that: the cases the script
checks, the rows the file lists, the owner's answer or the open decision in
words. A lead ID is dropped. Each replacement is one line under the index's
`## Notes`.

A check holds when its restatement keeps every case and a test written
from it fails before the fix. One that would not (it loses a case, or the
finding's evidence shows the code already does what it asks) holds its
fix, `waits: plan check`, with what is wrong in one line, for
`remediation-plan`; the other fixes go on.

## Creating

1. Write each ready fix's ticket to `tickets/R-NNN.md`, those for the
   tracker included.
2. A script in `tool-output/tickets/` checks every ticket: title and size
   as in the plan, closing line present, no workspace path, lead or
   question ID, URL, host, e-mail address or `<redacted>`. Its output is
   kept beside it.
3. When tickets go to the tracker, **ask once**, through the structured
   question tool when there is one: the tickets to create (fix, title,
   labels, what each is blocked by), then those kept local and those
   waiting, each with its reason. Only a clear yes creates; the auditor may
   strike lines. The answer goes in the index, verbatim, with its date.
   Without it, the files stay local. When nothing goes to the tracker,
   nothing is asked, and `allowed: n/a`.
4. Create in the plan's order, so a ticket waited for exists before the
   one waiting for it. Before each, search the tracker for the fix ID in
   the closing line: a ticket found is recorded, not created again. Each
   creation is scripted in `tool-output/tickets/run-create.sh`, through
   the tracker's CLI or MCP server, labels set at creation, the body sent
   kept beside it as `R-NNN.sent.md`, and recorded in the index as soon as
   it succeeds, so a run stopped midway resumes.

## Index

`tickets/index.md`, in the engagement's `language`, keys and states in
English:

```markdown
# Tickets
plan: 02-remediation-plan.md, generated <YYYY-MM-DD>
skill: tickets@<version>
tools: [<name@version>]
destination: <tracker: kind, project, visibility checked YYYY-MM-DD | local>
allowed: <"the auditor's yes, verbatim" (YYYY-MM-DD) | n/a>

| Fix | Ticket | Labels | Sent | State |
|---|---|---|---|---|
| R-001 | <tracker URL> | ready-for-agent, plateforme | 2026-10-17 | sent |
| R-010 | tickets/R-010.md | ready-for-human, plateforme | — | local: sensitive, tracker public |
| R-013 | — | — | — | waits: report item 3 |

## Notes
```

Rows in the plan's order. Labels live here and in the tracker, never in a
ticket's body; in a local run they are what the mapping gives, for the
auditor. `tools`: those whose output the index relies on. States: `sent`;
`local` with its reason (destination, sensitive, struck by the auditor);
`waits` with every reason (report item, fix, plan check); and on later runs,
for a sent ticket, `changed since sent`, `fix done` or `fix dropped`.
`## Notes`: the pointers replaced, the fixes the conventions would split,
any choice the skill left open.

## Later runs

A fix never gets a second ticket. The local files are regenerated from the
plan. A sent ticket whose regenerated body differs from `R-NNN.sent.md`
becomes `changed since sent`, with what changed in one line; one whose fix
became `done` or `dropped` says so. The auditor handles these in the
tracker. A new fix, or one no longer waiting, goes through Creating.

## End report

Tickets created, with their links; kept local, and why; waiting, and for
what (report item, fix, plan check, routed to its step); sent tickets
needing the auditor (changed, done, dropped); the labels set; and that
nothing else was written in the tracker.
