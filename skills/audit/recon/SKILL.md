---
name: recon
description: Map an unfamiliar codebase before auditing it (stacks, entry points, modules, execution flows, trust boundaries, personal-data flows, glossary). Use at the start of an audit, or when an audit axis needs codebase context and no codebase map exists yet.
---

# recon

Version: 0.24.0 (audit skills, see CHANGELOG)

Build the **codebase map** once, so every axis starts from the same
understanding. Input: `00-engagement.md` (missing: stop, ask for
`audit-kickoff`). Output: `<workspace>/01-codebase-map.md`. Bound by [rules of
engagement](../finding-format/rules-of-engagement.md).

Without the repository capability, map what the running target shows and say
so at the top.

## Working copy and dependencies

Work in the dedicated clone at the audited commit that kickoff recorded as
`working_copy`; without one, create it and give its path in the end report.
For each ecosystem of the project (Composer, npm, an import map...), take
the dependencies' code from the first available:

1. an existing install with a byte-identical lockfile (`cmp`) whose record
   of installed packages lists every locked one, path recorded;
2. an install into the clone that runs no package code (`composer install
   --no-scripts --no-plugins`, `npm ci --ignore-scripts`, or equivalent), the
   lockfile unchanged afterwards (`git status`);
3. neither: the questions left open go under Unknowns.

An ecosystem that only holds tooling outside the scope (test runners, agent
tools) is recorded as such and not installed.

## Strategy

With the profile's `graph_tool`, take structure from it (clusters, call
chains, flows), then read the code at every point the map relies on: a graph
can hold wrong edges, and each one goes under Unknowns. Without it, or with
its server unreachable, use its CLI, else go breadth first: manifests, entry
points, then inward until each module's role is clear. The map is the same
either way.

## The map

```markdown
# Codebase map
commit: <sha>
method: <graph tool name@version | search>
dependencies:
  <ecosystem>: <path of identical install | installed without scripts | absent | out of scope>
skill: recon@<version>
tools: [<name@version>]
generated: <YYYY-MM-DD>

## Stacks
## Entry points
## Modules
## Main execution flows
## Trust boundaries
## Personal data
## External dependencies
## Glossary
## Unknowns
```

- **Stacks**: languages, frameworks, runtimes, versions, where declared.
- **Entry points**: routes, commands, consumers, jobs, webhooks; file:line each.
- **Modules**: real units and duties; where structure departs from appearance.
- **Main execution flows**: those that carry the product, usually 5 to 12,
  entry to side effect, each with the pages or routes it covers, so every
  axis reads "main flow" the same way.
- **Trust boundaries**: untrusted input, authn and authz enforcement, outbound
  calls.
- **Personal data**: what; where it enters, is stored, leaves (logs, third
  parties, exports).
- **External dependencies**: services, APIs, stores, infrastructure.
- **Glossary**: domain terms as the code uses them.
- **Unknowns**: numbered; what, why it matters, "Settled by: <agent | auditor |
  owner>: <how>".

The agent settles by reading code or running an analysis tool; running the
project or stating an intent falls to the auditor or owner (for an
auditor-owned target, the auditor may paste a command's output).

## Rules

- Every statement carries a pointer: file and line, or a query and its
  result. The map's pointers need no quote; findings and leads quote theirs.
- A graph edge the map relies on is checked; one found wrong goes under
  Unknowns. Edges the map does not use are not inventoried.
- A graph tool may register its index outside the workspace (a registry
  entry): record where.
- The map describes. Problems seen on the way become short leads (observation,
  pointers, settling check) in the relevant `findings/<axis>.md`, in the
  engagement language; an axis outside the plan gets its file with coverage
  `not-requested`.
- A call no method shows is written "no caller found by <method>", under
  Unknowns, like every other gap.
