---
name: tickets
description: Turn the fixes of an audit's remediation plan into tickets, one per fix, in the target's issue tracker when the engagement allows it, as local files otherwise. Use after audit-report, or when asked for the tickets of an audit workspace.
---

# tickets

Version: 0.17.0 (audit skills, see CHANGELOG)

One **ticket** per open fix of the plan: the work handed to whoever does it,
where they track work. Input: `00-engagement.md`, `02-remediation-plan.md`,
`findings/*.md`, `reports/`, and the target's tracker when the engagement
names one. Output: `<workspace>/tickets/`, and new issues in that tracker.
Bound by [rules of engagement](../finding-format/rules-of-engagement.md).

A ticket is drawn from its fix and adds nothing: no finding, no grouping, no
remediation of its own. Once created in a tracker it belongs to the team:
this step never edits, comments on, relabels, closes or deletes it.

## Before starting

1. Read the engagement file and its `## Tickets`, `finding-format`, the
   plan, the conventions file it names, and in each fix's findings what a
   ticket carries: plain-language explanation, remediation, `sensitive`.
2. **Plan current**, as `audit-report` requires it (Before writing, step 2);
   otherwise `remediation-plan` first. No report yet: `audit-report` first.
3. **Ready fixes**: each `open` fix of the plan whose ID, and its
   findings' IDs, appear in no blocking item of the report's DRAFT list.
   A fix named there waits, with the item's number; a report without DRAFT
   leaves every open fix ready.
4. An existing `tickets/index.md` is updated, never rewritten from nothing
   (Later runs).

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

In the language the conventions ask for, the engagement's `language`
otherwise. When the engagement names a conventions file (an agent's guide
to the tracker, a contributing guide, issue templates), the ticket follows
it: sections, size, dependency links, labels among those `labels:` maps.
Otherwise:

```markdown
# <the fix's title>

## Why
<the consequence, from its findings' plain-language explanations>

## Change
<the fix's Change: the target state, in steps when several executors
take part; the locations where it lands>

## Acceptance criteria
- [ ] <each finding's check, from the fix's Check, as behaviour to test>

## Blocked by
<a fix waited for: its ticket, as the tracker links it, or its ID and
title; a decision: the question or decision in words>

## Size
<S: hours | M: days | L: weeks>

From the audit of <target> at <short commit> (<date>): fix R-001
(F-A11Y-008, F-PERF-008), severity medium.
```

The closing line is always there, whatever the conventions: it ties the
ticket to its fix, and a search for the fix ID finds it.

A ticket leaves the workspace, so it carries the target state and what to
test, never how the problem is exploited: no evidence, exploitation path,
payload, request that triggers it, secret, personal data, production host
or URL, or workspace path. A check names the kinds of input to test, not a
literal one ("a destination on another host, in every form the filter
accepts", not the string). A sensitive fix in a restricted tracker keeps
its files and checks under the same rule.

Labels and milestones: only those `labels:` maps, which exist in the
tracker; this step creates none.

## Creating

1. Write each ready fix's ticket to `tickets/R-NNN.md`, those for the
   tracker included.
2. **Ask once**, through the structured question tool when there is one:
   the tickets to create (fix, title, labels, what each is blocked by),
   then those kept local and those waiting, each with its reason. Only a
   clear yes creates; the auditor may strike lines. The answer goes in the
   index, verbatim, with its date. Without it, the files stay local.
3. Create in the plan's order, so a ticket waited for exists before the
   one waiting for it. Before each, search the tracker for the fix ID in
   the closing line: a ticket found is recorded, not created again. Each
   creation is scripted in `tool-output/tickets/run-create.sh`, through
   the tracker's CLI or MCP server, the body sent kept beside it as
   `R-NNN.sent.md`, and recorded in the index as soon as it succeeds, so
   a run stopped midway resumes.

## Index

`tickets/index.md`:

```markdown
# Tickets
plan: 02-remediation-plan.md, generated <YYYY-MM-DD>
skill: tickets@<version>
tools: [<name@version>]
destination: <tracker: kind, project, visibility checked YYYY-MM-DD | local>
allowed: "<the auditor's yes, verbatim>" (<YYYY-MM-DD>)

| Fix | Ticket | Sent | State |
|---|---|---|---|
| R-001 | <tracker URL> | 2026-10-17 | sent |
| R-010 | tickets/R-010.md | — | local: sensitive, tracker public |
| R-013 | — | — | waits: report item 3 |
```

States: `sent`; `local` with its reason (destination, sensitive, struck by
the auditor); `waits` with the report item; and on later runs, for a sent
ticket, `changed since sent`, `fix done` or `fix dropped`.

## Later runs

A fix never gets a second ticket. The local files are regenerated from the
plan. A sent ticket whose regenerated body differs from `R-NNN.sent.md`
becomes `changed since sent`, with what changed in one line; one whose fix
became `done` or `dropped` says so. The auditor handles these in the
tracker. A new fix, or one no longer waiting, goes through Creating.

## End report

Tickets created, with their links; kept local, and why; waiting, and for
which report item; sent tickets needing the auditor (changed, done,
dropped); the labels set; and that nothing else was written in the tracker.
