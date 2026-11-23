---
name: review-pr
description: Review a pull request, a branch or a base..head range, typically a coding agent's pull request, and write a brief of where to read and why, what the review did not cover, and a proposed verdict (merge, fix, close-and-reprompt), in a run directory outside the repository. Use when asked to review a PR number, a branch, an agent's PR or the changes between two refs, before reading the diff line by line.
---

# review-pr

Version: 0.1.0 (review skills, see CHANGELOG)

One review run on a pull request, a branch or a `base..head` range. It never decides: it
tells the reviewer where to look, what was not checked, and proposes a
verdict the reviewer takes or leaves. The run directory, the review finding
and the brief are described in [run-directory.md](run-directory.md).

This version runs the git file-change signals, a bucket for every changed
file, the coverage gaps, the brief and the verdict. The risk map
`review-setup` writes is read at the base: a changed file in a risk zone
names its zone and is never `skim`. The run finds what the change was
supposed to do: the PR body, the spec and the tickets, each checked against
the Pocock contract ([pocock-contract.md](pocock-contract.md)) when it is
read. One judgment step exists, `intent` ([steps/intent.md](steps/intent.md)):
each acceptance criterion mapped to the hunks that implement it, each
changed file justified by a ticket or flagged out of scope, each change
against the spec's decisions flagged. No content detector and no
`contracts` or `structure` step exists yet, so every changed file is
`unproven` unless a finding marks it `must-read`, and the brief says which
dimensions did not run.

## Invariants

Not settings (ADR 0006 of `Birdiz/skills`, the review invariants):

1. The reviewed branch is never written to: no commit, no fix, no file in
   the working copy. Trees are read from git objects, never checked out;
   the run directory lives under the user's state directory.
2. Coverage gaps are always reported: a missing tool, a missing stack
   adapter, a dimension not in this version, a contract drift.
3. "Skim" needs deterministic evidence. A judgment step can move a file up,
   to `must-read` or `glance`, by raising a finding; never down to `skim`.

## Run

Scripts are in `scripts/`, run with `python3 -I`, standard library only.

1. **Target.** A PR number, a branch (compared with the remote's default
   branch, else `main`, else `master`) or a range `base..head`. Only this
   skill asks questions: when the user names none, or the default branch is
   not the base they mean, ask, with an example (`--pr 52`,
   `main..feature/login`).
2. **Start the run.**
   `python3 -I scripts/run.py --pr <number> --repo <repository>`, or
   `python3 -I scripts/run.py <branch | base..head> --repo <repository>`.
   A PR is read with `gh`; its head is fetched by ref when missing, never
   checked out. The run refuses an empty diff and an unknown ref or PR
   (exit 2, nothing written): say so and stop. Otherwise it prints the
   tools found on this machine, the `sources:` lines (how the spec and
   tickets were found, and the intent status), the verdict line, a
   `STEP: <step> <step file>` line for each judgment step to run and, last,
   `RUN: <run directory>`.
   - The spec and tickets are found from the PR's closing references, then
     issue references in the commits, then a spec file named after the
     branch. An `ASK:` line means none was found: ask the user once where
     the spec is, with examples (an issue `#35`, a path such as
     `.scratch/login/spec.md`, or "there is none"), then run again with
     `--spec <#N | path>` or `--no-spec`. The same head is the same round.
   - A `contract drift` in the `sources:` lines is not a failure. The
     artifact no longer has a section the review relies on, and the
     dimension it feeds is `not-evaluable`. Report it as written; never
     guess what the drifted section meant.
3. **Run the judgment steps.** For each `STEP:` line, start a sub-agent
   with fresh context, and give it only the step file's path and the run
   directory: "Follow `<step file>` on the run directory `<run>`." It reads
   files and writes its findings file, and asks nothing. Without
   sub-agents, follow the step file yourself, in order, after the run, one
   step at a time. No `STEP:` line for `intent` means its sources are not
   evaluable (no spec, contract drift): `run.py` already wrote its
   coverage with the reason, and the verdict says intent was not checked.
   Then `python3 -I scripts/brief.py <run>`.
4. **Check the run.** `python3 -I scripts/validate.py <run> --require brief --require intent`,
   then `python3 -I scripts/check-pointers.py <run>`. An `ERROR`,
   `MISMATCH` or `MISSING` line is a defect of the run: report it, never
   edit the brief to hide it. The brief is a projection: when a findings
   file changes, run `python3 -I scripts/brief.py <run>`, never edit
   `brief.md` by hand.
5. **Present the brief.** Give the run directory, then the brief's sections
   in order, the coverage gaps in full (the spec and tickets found, any
   contract drift) and the verdict line as written, with its round. Do not
   soften `unproven`: it means read the file, since nothing proved it safe.
   A `close-and-reprompt` for misread intent names the criteria not found,
   the files out of scope or the decisions broken: give them as written.

Running again on the same head replaces its run directory and is not a new
round; a new head of the same branch is. Nothing else is kept between runs.
