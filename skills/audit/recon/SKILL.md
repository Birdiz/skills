---
name: recon
description: Map an unfamiliar codebase before auditing it (stacks, entry points, modules, execution flows, trust boundaries, personal-data flows, glossary). Use at the start of an audit, or when an audit axis needs codebase context and no codebase map exists yet.
---

# recon

Build the **codebase map** once, so every axis works from the same
understanding instead of rebuilding its own.

Input: `00-engagement.md` (stop if missing, ask for `audit-kickoff`).
Output: `<workspace>/01-codebase-map.md`

If the engagement has no repository capability, write a map limited to what
the running target shows, and say so at the top.

## Working copy

Work on a dedicated clone at the audited commit, never on the client's
working tree. Index files, caches and tool output (for example a `.gitnexus/`
directory) stay in that clone or in the workspace.

## Strategy

Check the auditor profile for `graph_tool`.

- **Graph tool available**: use it for structure (clusters, call chains,
  execution flows), then read the code at every point the map relies on.
- **No graph tool**: go breadth first. Manifests and lockfiles, then entry
  points, then follow each entry point inward. Stop descending when a module's
  role is clear.

Either way the map has the same sections. The tool changes the cost, not the
result.

## What the map contains

```markdown
# Codebase map
commit: <sha>
method: <graph tool name@version | search>
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
What could not be determined, and what would settle it.
```

## Rules

**Every statement carries a pointer.** File and line, or a query and its
result. A map that cannot be checked will be trusted anyway, and wrongly.

**The map describes, it does not judge.** Problems noticed along the way go
to `## Leads` in the relevant `findings/<axis>.md`, in `finding-format`. They
are not findings yet.

**A missing edge is an unknown, not a fact.** Dependency injection, event
subscribers, config-driven routing, reflection and templates do not show up
as calls. Write "no caller found by <method>" under Unknowns, not "unused".

**Write unknowns down.** An honest gap in the map becomes a line in the
report's coverage. A silent one becomes a false sense of completeness.

**Read only.** Nothing is modified in the audited code, including formatting,
dependency installation that rewrites lockfiles, or generated files.
