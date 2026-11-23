# 0007: The review reads Pocock's artifacts under a written contract

Status: accepted, 2026-11-23

## Context

`birdiz-review` judges a pull request against what it was supposed to do.
The spec, the tickets, the PR body and the tracker doc that says where they
live are written by Matt Pocock's skills (`to-spec`, `to-tickets`, `pr`,
`setup-matt-pocock-skills`). Upstream changes its templates without
notice, and its `SCOPE.md` rejects configuration options, so the review
can't ask for a stable format. Old artifacts are never rewritten either:
one PR can link a spec in last month's format and tickets in this week's.

A review that guesses when a section moved would judge the task wrongly
without saying so. A review that stops on the first unexpected heading
would be useless after every upstream release.

## Decision

1. **Artifacts only.** The review reads Pocock's artifacts and never
   invokes a Pocock skill or writes an artifact. Nothing is proposed
   upstream.
2. **A written contract.** `pocock-contract.md` in the review plugin lists
   each artifact read, the sections relied on, and the upstream commit last
   checked (`abeeaf9` first). `pocock.py` implements that list, and
   `review-setup` uses the same code for the docs it checks.
3. **Checked per artifact, when read.** Each spec, ticket, PR body or
   tracker doc gets its own status: `ok`, `drift` (what is missing), or
   `unreadable` (why). Drift belongs to an artifact, not to a run.
4. **Drift degrades visibly.** An artifact that drifted makes its dimension
   `not-evaluable (contract drift: <artifact>, <what>)`. The run goes on,
   and the brief's coverage gaps say so (ADR 0006, invariant 2).
5. **Absent is not drift.** A PR body without `Merge Danger` is "not
   declared". A GitHub ticket without `Parent` or `Blocked by` sections uses
   native relations. A glossary or ADR directory not created yet makes its
   dimension not-evaluable, as Pocock creates them lazily.
6. **A fixed order to find the spec.** The user's answer, then the PR's
   closing references, then issue references in the commits, then a spec
   file named after the branch, then asking. Only `review-pr` asks.

## Consequences

- An upstream template change shows up as a contract drift in the briefs
  that read the new format. The fix is a contract update with the new
  upstream commit; nothing breaks in the meantime.
- Fixture artifacts in each template, with native and body-text relations,
  and PR bodies with and without `Merge Danger`, are part of the tests. A
  renamed section must produce `not-evaluable (contract drift: ...)`.
- Trackers other than GitHub and local markdown are named by the tracker
  doc but not read in this version. Intent says so instead of guessing.
