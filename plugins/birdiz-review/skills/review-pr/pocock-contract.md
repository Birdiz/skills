# The Pocock artifact contract

The review reads artifacts that Matt Pocock's skills write
(`mattpocock/skills`). It never writes them and never invokes those skills.
This file lists each artifact the review reads and the sections it relies
on. `scripts/pocock.py` implements the list.

Upstream commit last checked: **`abeeaf9`** (v1.3.2, recorded as
`mattpocock/skills@abeeaf9` in each run's `sources.json`). When upstream
changes a template, check it against this file, update both, and record the
new commit here and in `pocock.UPSTREAM`.

The decision is in ADR 0007 of `Birdiz/skills` (the Pocock artifact
contract).

## Rules

- **Each artifact is checked when it is read.** A Pocock update does not
  rewrite old artifacts, so one PR can link a spec in an old format and
  tickets in a new one. Drift belongs to an artifact, not to a run.
- **Drift makes a dimension not-evaluable, and the run continues.** Its
  coverage becomes `not-evaluable (contract drift: <artifact>, <what>)`,
  and the brief's coverage gaps say so.
- **Absent is not drift.** A PR body without `Merge Danger` is "not
  declared". A GitHub ticket without `Parent` or `Blocked by` sections uses
  native relations. A glossary or ADR directory that does not exist yet was
  never created (Pocock creates them lazily).

## Artifacts

| Artifact | Written by | Read by | Relied on |
|---|---|---|---|
| Tracker doc `docs/agents/issue-tracker.md` | `setup-matt-pocock-skills` | `review-setup`, `review-pr` (at the base) | title `# Issue tracker: <GitHub \| GitLab \| Local Markdown>`; a `## When a skill says "fetch the relevant ticket"` section |
| Domain doc `docs/agents/domain.md` | `setup-matt-pocock-skills` | `review-setup`, `review-pr` (structure step, at the base) | names `GLOSSARY.md` or `GLOSSARY-MAP.md`, and an ADR directory |
| Glossary `GLOSSARY.md` | `domain-modeling` | `review-pr` (structure step, at the head) | `**Term**:` at the start of a line (or a list item); `_Avoid_:` words under it |
| Glossary map `GLOSSARY-MAP.md` | `domain-modeling` | `review-pr` (structure step, at the head) | links `[Context](./path/GLOSSARY.md)` to each context's glossary |
| ADRs `docs/adr/NNNN-slug.md` | `domain-modeling` | `review-pr` (structure step, at the head) | Markdown files in the directories the domain doc names; read as prose, no section relied on |
| Spec | `to-spec` | `review-pr` | `## Implementation Decisions`, `## Testing Decisions`, `## Out of Scope` |
| Ticket, issue template | `to-tickets` | `review-pr` | `## What to build`; `## Acceptance criteria` with `- [ ]` items; `## Parent` and `## Blocked by` only when not native |
| Ticket, local file template | `to-tickets` | `review-pr` | `# <NN>: <title>`; `**What to build:**`; bare `- [ ]` items |
| PR body | `pr` (when the model picks it) | `review-pr` | `## Merge Danger` with `**Door:** one-way \| two-way` and `**Blast Radius:** <word>` |

### Tracker doc

Read as committed at the base, from git objects. Whoever ran setup wrote
it, so its shape varies between versions. A doc written by 1.3.1 has its
`Blocking` operation only under the wayfinding section. Nothing here
depends on blocking relations.

- `GitHub`: issues are read with `gh issue view <n> --json ...`, with
  `parent` and `subIssues` when the local `gh` has them (2.94+).
- `Local Markdown`: specs and tickets are files under `.scratch/` in the
  head tree. Issue numbers name nothing there, so only files are looked
  for.
- `GitLab`, or a freeform tracker with no template: issues are not read in
  this version, and intent is `not-evaluable` with the reason.
- A missing doc means no issue is read. A doc without the "fetch the
  relevant ticket" section is drift.

### Finding the spec and tickets

The first rule that finds something wins:

1. the user's answer (`--spec #N`, `--spec <path>`, or `--no-spec`);
2. the closing references in the PR body, GitHub's keywords, one per
   reference (`implement-spec` marks its PR as closing the spec and
   tickets), with the PR's linked issues;
3. issue references (`#N`) in the commit messages of the diff, merges left
   out;
4. a spec file under `docs/`, `specs/` or `.scratch/` whose directory or
   file name is the branch's name (a trailing `-<hex>` suffix ignored);
5. nothing: `review-pr` asks the user.

An issue's role comes from its relations when they say it: a ticket's
parent is the spec, and a spec's sub-issue is a ticket. Without relations,
its sections decide. A spec's tickets are its sub-issues. Without native
sub-issues, they are the issues whose body has a `Part of #<spec>` line.
For a local spec, they are the files in the `issues/` directory beside it.
The tickets the PR closes are in scope. When the spec itself was named,
closed or found as a file, all its tickets are in scope; the others are
siblings, read for the intent step's scope check.

### Domain doc, glossary and ADRs

The domain doc is read as committed at the base, like the tracker doc, so
a branch can't move the glossary or the ADRs it names. The glossary and the
ADRs are read at the head: a term or an ADR the diff adds counts.

- A missing domain doc is not drift: the structure step reads Pocock's
  defaults (`GLOSSARY.md` or `GLOSSARY-MAP.md` at the root, `docs/adr/`).
  A doc that names no glossary, names only the legacy `CONTEXT.md`, or
  names no ADR directory is drift for the area it feeds (`Glossary` or
  `ADRs`).
- An ADR directory template such as `src/<context>/docs/adr/` is matched
  against the head tree, and each glossary of the map adds its own
  `<context>/docs/adr/`.
- A glossary or ADR directory that does not exist, or holds nothing, was
  never created: `not-evaluable (no glossary)` or `not-evaluable (no
  ADRs)`, never drift. A glossary that exists with no `**Term**:` line, or
  a map that links no glossary, is drift: the review does not guess
  another format.

### Spec

The `to-spec` template's sections are Problem Statement, Solution, User
Stories, Implementation Decisions, Testing Decisions, Out of Scope and
Further Notes. The review relies on three of them: Implementation
Decisions, Out of Scope (both for intent) and Testing Decisions (for test
integrity, a later slice). Missing any of the three is drift.

### Tickets

The acceptance criteria are the checkbox items. In the issue template they
sit under `## Acceptance criteria`. In the local file template they are
bare. On GitHub the parent and blockers are native relations, and the body
leaves their sections out. Their absence is not drift; a `Part of #N` line
stands in for a parent where sub-issues are unavailable. A ticket in the
issue template without `## Acceptance criteria`, or with no checkbox under
it, is drift. So is a local ticket with no checkbox.

### PR body

`implement-spec` opens its PR without the `pr` skill, and `pr` runs only
when the model picks it. A body without `## Merge Danger` is therefore "not
declared", which the brief states. `Door` is compared mechanically and must
read one-way or two-way. `Blast Radius` is one free word, shown beside what
was detected. Merge Danger without either line, a Door that is neither
value, or a `**Door:**` line outside Merge Danger is drift.
