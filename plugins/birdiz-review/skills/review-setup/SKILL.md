---
name: review-setup
description: Record a repository's review facts once (stacks, and the risk map of path globs mapped to risk zones) in docs/agents/review.md, after checking the Pocock artifacts the review reads. Run before the first review-pr in a repo, or when review-pr reports a missing or broken review.md.
disable-model-invocation: true
---

# review-setup

Version: 0.1.0 (review skills, see CHANGELOG)

Write the **repo facts** the review reads: the stacks, and the **risk map**,
path globs mapped to **risk zones**. A changed file in a risk zone is never
`skim` in a review brief.

Output, and nothing else:
- `docs/agents/review.md`;
- a `### Review` subsection inside the `## Agent skills` block of `CLAUDE.md`
  or `AGENTS.md`, which Pocock's `setup-matt-pocock-skills` creates.

Both are committed by the user, on a branch of their own. Tool versions and
the run root are machine facts: they are never written here.

## Process

1. **Detect**: `python3 -I <this skill>/scripts/detect.py <repo>`. It writes
   nothing and reports:
   - the write guard. When it says `REFUSED` (detached HEAD, the head of an
     open PR, or a branch `review-pr` has a run for), give the reasons, ask
     the user to switch to a branch of their own, and stop: never write into
     a branch under review;
   - the stacks, each with the manifest or files that show it;
   - the detector tools this machine has. Say they are not stored:
     `review-pr` detects them again on every run;
   - the Pocock artifacts, each `ok`, `missing`, `drift`, `unchecked`
     (freeform tracker) or `absent` (glossary or ADRs not created yet, which
     Pocock does lazily: not a problem). For each `missing` or `drift`, say
     what is missing and that `setup-matt-pocock-skills` fixes it. With no
     `## Agent skills` block there is nowhere to write: stop there;
   - the proposed risk zones, each with a pointer to what suggested it (a
     directory name, a file name, or `file:line` and the line);
   - the current `review.md`, if any.
2. **Confirm the stacks** in one message, asking only about doubtful ones.
3. **Confirm the risk map in rounds**, at most three questions a round, each
   with a recommended answer ("1 ok, 2 drop, 3 ok"), through the agent's
   structured question tool when it has one:
   - start from the current `review.md` when it exists, and show which
     proposals are new;
   - show each proposal as zone, glob and pointer; the user keeps, drops,
     narrows or widens it;
   - ask once whether a zone has places the detection missed. Zones are
     `auth`, `personal-data`, `payments`, `concurrency`, `irreversible`,
     `public-api`, or another lowercase-hyphen name the user gives.
4. **Write** only what the user confirmed:
   `python3 -I <this skill>/scripts/write.py <repo> --stack <name>... --zone '<glob>' <zone>...`
   It replaces `review.md`, sets the `### Review` subsection in place
   without touching the other subsections, and refuses (writing nothing)
   under the same guard as step 1. Show what it wrote and remind the user to
   commit it.

## Globs

Gitignore-like, relative to the repository root, quoted in the shell:
- `*` stays inside one directory, `?` is one character, `[ab]` a class;
- `**` spans directories: `src/Security/**`, `**/Billing/*.php`;
- a glob with no `/` matches a name at any depth: `*.sql`, `migrations`;
- a trailing `/` matches directories only; a matched directory covers every
  file under it;
- no negation (`!`).
