---
name: recon
description: Map an unfamiliar codebase before auditing it (stacks, entry points, modules, execution flows, trust boundaries, personal-data flows, glossary). Use at the start of an audit, or when an audit axis needs codebase context and no codebase map exists yet.
---

# recon

Version: 0.4.0 (audit skills, see CHANGELOG)

Build the **codebase map** once, so every axis works from the same
understanding instead of rebuilding its own.

Input: `00-engagement.md` (stop if missing, ask for `audit-kickoff`).
Output: `<workspace>/01-codebase-map.md`

If the engagement has no repository capability, write a map limited to what
the running target shows, and say so at the top.

## Working copy

Work on a dedicated clone at the audited commit, never on the client's
working tree. Record its path as `working_copy` in the engagement file. Index
files, caches and tool output (for example a `.gitnexus/` directory) stay in
that clone or in the workspace.

### Dependency source code

Framework defaults decide many security questions, so the map is better with
the dependencies' code at hand. In order of preference:

1. An existing install whose lockfile is byte-identical to the audited one
   (check with `diff`, record the path).
2. An install into the dedicated clone that runs no project or package code:
   `composer install --no-scripts --no-plugins`, `npm ci --ignore-scripts`, or
   the ecosystem's equivalent. Check afterwards that the lockfile is unchanged
   (`git status`). This downloads third-party code; nothing executes.
3. Neither: list the questions this leaves open under Unknowns.

Record which one was used at the top of the map.

## Strategy

Check the auditor profile for `graph_tool`.

- **Graph tool available**: use it for structure (clusters, call chains,
  execution flows), then read the code at every point the map relies on. A
  graph can be wrong, not only incomplete: verify each edge the map uses, and
  record any wrong edge under Unknowns.
- **No graph tool**, or its server unreachable: use its CLI if there is one,
  otherwise go breadth first. Manifests and lockfiles, then entry points, then
  follow each entry point inward. Stop descending when a module's role is
  clear.

Either way the map has the same sections. The tool changes the cost, not the
result.

## What the map contains

```markdown
# Codebase map
commit: <sha>
method: <graph tool name@version | search>
dependencies: <path of identical install | installed without scripts | absent>
generated: <YYYY-MM-DD>

## Stacks
Languages, frameworks, runtimes, with versions and where they are declared.

## Entry points
Everything that starts execution: HTTP routes, CLI commands, queue consumers,
scheduled jobs, webhooks. One line each, with file and line.

## Modules
The real units and what each one is responsible for. Then: where the real
dependency structure differs from the documented or apparent one.

## Main execution flows
The five to ten flows that carry the product, each as a short chain from
entry point to side effect, with pointers.

## Trust boundaries
Where untrusted input enters, where authentication and authorization are
enforced, where the system calls out to third parties.

## Personal data
Which personal data is handled, where it enters, where it is stored, where it
leaves (logs, third parties, exports).

## External dependencies
Services, APIs, data stores, and the infrastructure definitions if present.

## Glossary
Domain terms as the code uses them, one line each.

## Unknowns
Numbered. Each one: what could not be determined, why it matters, and
"Settled by: <agent | auditor | owner>: <how>".
```

"Settled by" names who can act. The agent can read more code or run an
analysis tool. Only the auditor or the owner can run the project (a console
command, a built image) or state an intent; for an auditor-owned target, the
auditor can paste the output of a command the agent may not run.

## Rules

**Every statement carries a pointer.** File and line, or a query and its
result. A map that cannot be checked will be trusted anyway, and wrongly.

**The map describes, it does not judge.** Problems noticed along the way go
to `## Leads` in the relevant `findings/<axis>.md`, in `finding-format`. Keep
them short: the observation, the pointers, and the check that would settle
it. The investigation belongs to the axis, which closes every lead.

**Leads for axes outside the plan** go to that axis's file too, with coverage
`not-requested`, so they are not lost and not mistaken for an assessment.

**A missing edge is an unknown, not a fact.** Dependency injection, event
subscribers, config-driven routing, reflection and templates do not show up
as calls. Write "no caller found by <method>" under Unknowns, not "unused".

**Write unknowns down.** An honest gap in the map becomes a line in the
report's coverage. A silent one becomes a false sense of completeness.

**Read only.** Nothing is modified in the audited code, including formatting,
dependency installation that rewrites lockfiles, or generated files.
