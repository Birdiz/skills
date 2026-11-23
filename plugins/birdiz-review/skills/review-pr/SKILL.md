---
name: review-pr
description: Review a branch or a base..head range, typically a coding agent's pull request, and write a brief of where to read and why, what the review did not cover, and a proposed verdict (merge, fix, close-and-reprompt), in a run directory outside the repository. Use when asked to review a branch, an agent's PR or the changes between two refs, before reading the diff line by line.
---

# review-pr

Version: 0.1.0 (review skills, see CHANGELOG)

One review run on a branch or a `base..head` range. It never decides: it
tells the reviewer where to look, what was not checked, and proposes a
verdict the reviewer takes or leaves. The run directory, the review finding
and the brief are described in [run-directory.md](run-directory.md).

This version is the bare run: the git file-change signals, a bucket for
every changed file, the coverage gaps, the brief and the verdict. No content
detector and no judgment step (`intent`, `contracts`, `structure`) exists
yet, so every changed file is `unproven` and the brief says which
dimensions did not run.

## Invariants

Not settings (ADR 0006 of `Birdiz/skills`, the review invariants):

1. The reviewed branch is never written to: no commit, no fix, no file in
   the working copy. Trees are read from git objects, never checked out;
   the run directory lives under the user's state directory.
2. Coverage gaps are always reported: a missing tool, a missing stack
   adapter, a dimension not in this version.
3. "Skim" needs deterministic evidence. A judgment step can move a file up,
   to `must-read` or `glance`, by raising a finding; never down to `skim`.

## Run

Scripts are in `scripts/`, run with `python3 -I`, standard library only.

1. **Target.** A branch (compared with the remote's default branch, else
   `main`, else `master`) or a range `base..head`. Only this skill asks
   questions: when the user names neither, or the default branch is not the
   base they mean, ask, with an example (`main..feature/login`).
2. **Start the run.** `python3 -I scripts/run.py <target> --repo <repository>`.
   It refuses an empty diff and an unknown ref (exit 2, nothing written):
   say so and stop. Otherwise it prints the tools found on this machine,
   the verdict line and, last, `RUN: <run directory>`.
3. **Check the run.** `python3 -I scripts/validate.py <run> --require brief`,
   then `python3 -I scripts/check-pointers.py <run>`. An `ERROR`,
   `MISMATCH` or `MISSING` line is a defect of the run: report it, never
   edit the brief to hide it. The brief is a projection: when a findings
   file changes, run `python3 -I scripts/brief.py <run>`, never edit
   `brief.md` by hand.
4. **Present the brief.** Give the run directory, then the brief's sections
   in order, the coverage gaps in full and the verdict line as written,
   with its round. Do not soften `unproven`: it means read the file, since
   nothing proved it safe.

Running again on the same head replaces its run directory and is not a new
round; a new head of the same branch is. Nothing else is kept between runs.
