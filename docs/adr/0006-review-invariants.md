# 0006: Review invariants

Status: accepted, 2026-11-23

## Context

`birdiz-review` reads a pull request, most often written by a coding agent,
and tells its reviewer where to read, why, and what was not checked. The
reviewer trusts the brief to spend attention: a file it calls safe to skim
is a file they will not read. Three ways of breaking that trust are
tempting because each looks like a convenience: fixing what the review
found, leaving out a check that could not run, and letting the model call a
file harmless. ADR 0003 already says rules with one legitimate answer are
not settings; these are the review's.

## Decision

1. **The reviewed branch is never written to by the review**: no commit, no
   fix, no file in the working copy. Trees are read from git objects, never
   checked out, and each run is written to a directory under the user's
   state directory, never inside the repository. A review that changes what
   it reviews has reviewed something else, and the working copy may hold
   the reviewer's own unfinished work.
2. **Coverage gaps are always reported**: a missing tool, a missing stack
   adapter, a dimension not in this version, a contract drift. An unreported
   gap reads as a clean result, and a `merge` verdict is always printed with
   the dimensions that did not run.
3. **"Safe to skim" requires deterministic evidence.** A file is `skim` only
   when at least one content detector able to read its file type covered
   it, every applicable detector covered it and found nothing, no finding
   points at it, and it is outside the risk map. A file no detector could
   cover is `unproven`, to be read. The model alone can move a file up, to
   `must-read` or `glance`, by raising a finding; it can never move one to
   `skim`.
4. **Tests are judged from the spec without the implementation in
   context.** Recorded now for the test-integrity slice: a model that has
   read the code finds the tests that mirror it convincing.
5. **Adversarial review comes from a context that did not produce the
   change, on a different model.** Recorded now for the adversarial slice:
   the same context, or the same model, shares the blind spots that made
   the change.

## Consequences

- No repository file or option turns these off; the run root is a fixed
  default, not a setting.
- The validator enforces the third: a `skim` entry must name the content
  detector outputs that covered the file, and fails when any applicable
  detector did not, when a detector signalled on it, or when a finding
  points at it.
- Until content detectors exist, every changed file is `unproven`. That is
  the honest result, and the brief says why.
- Re-running on the same head replaces its run directory; the round count
  is derived from the run directories, so no other state is kept.
