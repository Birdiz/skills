# 0005: Two plugins share one finding core, copied into each

Status: accepted, 2026-11-23

## Context

The audit skills were one plugin, installed from the repository root. A
second set of skills, the review of a pull request, needs the same notion of
a finding: evidence, finding and lead, severity and confidence, coverage,
`sensitive`, `promptable`, the pointer and quote check. Anyone who wants only
audits, or only reviews, should not have to carry every skill's description
in every session.

A plugin installs as its own directory, copied into a cache, and reads
nothing outside it. A skill's scripts cannot reach a file of another plugin
by a relative path, and an installed plugin cannot rely on another one being
installed.

## Decision

- One repository and one marketplace (`birdiz`), one plugin per directory
  under `plugins/`: `birdiz-audit` (the former `birdiz-skills`), later
  `birdiz-review`. Each marketplace entry's source is its plugin's
  directory, so installing one copies only that one.
- The finding core lives once, in `core/` at the repository root, and is
  edited only there. `tools/sync_core.py` copies it to `core/` at the root of
  every plugin the marketplace lists; `--check` fails when a copy differs
  from the source, and CI runs it.
- A plugin's entry points find the nearest `core/finding_core/` above them,
  and never look past their plugin's root, so they import the copy that
  ships with them.
- No third `birdiz-core` plugin. A mandatory second install is a step people
  forget, and the core would then depend on resolution between plugins,
  which the plugin system does not guarantee.
- The core is a library and reference files, never a skill: installing both
  plugins duplicates no skill, only the copy of the core.

## Consequences

- A rule fixed in the core reaches both plugins at the next sync; a copy
  edited in place fails CI instead of drifting silently.
- Each installed plugin carries a few files the other also carries. Two
  plugins installed at different versions may carry different cores; each
  validator prints the core's version (`finding-core@x.y.z`) so a report
  says which one ran.
- Each plugin keeps its own version and changelog; the core has its own
  version.
- Renaming the plugin changed the install name and every `/birdiz-skills:`
  command, a breaking change with a migration note (0.27.0), while workspace
  files (ADR 0001) did not change.
