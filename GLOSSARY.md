# Glossary

Shared vocabulary for these skills. Use these terms as defined, in skills,
findings and reports.

## Core

Shared by every plugin: a finding means the same thing in a review as in an
audit.

- **Plugin**: one installable set of skills with its own directory,
  version and changelog (`birdiz-audit`, `birdiz-review`). Each
  carries its own copy of the finding core, synced from `core/`.
- **Finding**: an observed, evidenced problem in the common schema.
- **Lead**: a suspicion without evidence. Not reportable as a finding. The
  owning axis closes each one: promoted, closed, or open.
- **Finding core**: the part of that schema every plugin shares (evidence,
  finding and lead, status owned by a verifier, severity and confidence,
  coverage, `sensitive`, `promptable`, ID shapes, the pointer and quote
  check), with its own version. A plugin's **extension** adds its axes,
  keys, prose sections, section order and workspace layout.
- **Axis**: one dimension a plugin evaluates, with its own code in IDs;
  each plugin's extension lists its axes. In an audit: app security,
  accessibility, ...; one axis, one findings file.
- **Coverage**: what an axis evaluated, partially evaluated, could not
  evaluate, or was not asked to evaluate.
- **Sensitive**: a finding that would help an outside attacker or expose
  personal data if leaked. Confidential report only.
- **Promptable**: a finding whose remediation a coding agent could apply.
- **Invariant**: a rule no setting can turn off.

## Audit

The `birdiz-audit` plugin's own vocabulary.

- **Auditor profile**: what is stable for one auditor across audits (agent,
  tools, severity scale, language). Written by `audit-setup`.
- **Engagement**: one audit of one target for one audience. Described by the
  engagement file, written by `audit-kickoff`.
- **Workspace**: the directory holding one engagement's files. Never inside
  the audited repository, never inside this one.
- **Capability**: a kind of access available for an engagement: repository,
  running URL, cloud read access, client answers.
- **Evidence regime**: how an axis can prove something. *Static* (the
  repository is enough), *dynamic* (needs a running target), *declarative*
  (needs answers from the client).
- **Declared**: what rests only on the owner's answer. An answer that
  reveals a gap supports a declarative finding; one that claims a control
  closes a lead as declared, not observed, and the reports list it apart.
- **Lead pass**: an axis taking up, after it ran, the leads moved into its
  file and the answers to its questions; it touches only what they
  concern, and what it changes is verified again.
- **Proposal**: the answer the repository suggests to a question, with its
  pointer; the owner accepts or corrects it. A fact only the owner knows
  has none.
- **Codebase map**: the shared description of the audited code, written once
  by `recon` and read by every axis.
- **Fix**: one piece of work (a pull request, a session in a console, a
  decision) resolving one or more confirmed findings, `R-<NNN>`; its
  findings share one change, or the same files and executor.
- **Remediation plan**: the ordered fixes of an engagement, with who does
  each and what it waits for. Written by `remediation-plan`.
- **Ticket**: one fix handed to whoever does it, in the target's issue
  tracker when the owner allows it, a local file otherwise; drawn from the
  fix, never carrying how the problem is exploited, and the team's once
  created. Written by `tickets`.
- **Quick win**: an open fix of medium severity or above, small effort,
  waiting for nothing. Derived, not stored.
- **Resolution**: what the owner did about a finding: open, accepted (kept by
  decision), or fixed (verified at a later commit). Independent of status.
- **Rules of engagement**: what an audit step may touch and run: read-only
  repository, no execution of the project unless its owner allows it on their
  own target, passive by default, active only on authorized hosts.
- **Execution**: what the engagement lets an agent run of the project: nothing
  (`none`), its tests in a throwaway copy (`disposable-copy`), or also the
  target (`local-target`). More than `none` only on the auditor's own target.
- **Exposure**: who uses the target today. Recorded at kickoff; it lowers no
  rating.
- **Priority**: an owner's decision to do a fix before a planned change it
  does not block. It orders the plan and leaves severity alone.
- **Holding item**: a report problem that can change only one low-severity
  fix nothing else waits for. It holds that fix, without a DRAFT.
- **Reservation**: what still blocks after the round that follows a DRAFT.
  The report is final, says so at the top, and the fixes concerned stay held.
- **Projection**: a deliverable derived from the findings files alone; it adds
  no analysis and is regenerated, never edited, when they change.
- **Peer report**: the complete, confidential deliverable for a technical
  reader.
- **Summary**: the plain-language deliverable for a decision maker; confirmed
  findings only, sensitive ones by consequence only.
- **Remediation prompt**: a self-contained instruction for a coding agent or
  a developer, describing the target state, never the attack.

## Review

The `birdiz-review` plugin's own vocabulary.

- **Review run**: one review of one head of a branch or range, written to a
  **run directory** keyed by repository, branch and head short sha, under
  the user's state directory and never inside the reviewed repository. A
  new run on the same head replaces it.
- **Run header**: what a run records about itself: the target, base, head
  and merge base, the diff, and the detector tools found on this machine
  with their versions.
- **Detector**: a standard-library script that reads the diff and writes a
  JSON output with its own coverage (the files it could judge, the ones it
  could not and why) and its signals. A **content detector** reads what a
  file's content means, for the file types it declares; a stack-agnostic
  signal, such as the git file changes, only says a file changed in a
  notable way. The stack-agnostic content detectors read migrations,
  configuration and environment templates, routes, OpenAPI and GraphQL
  contracts, dependency manifests and lockfiles, and test assertions. Each
  uses its tool (`squawk`, `oasdiff`, `graphql-inspector`) when the machine
  has it, and its heuristic otherwise, saying so in its coverage. A
  **stack adapter** reads a language's code: the PHP, TypeScript and
  Python adapters' content detectors are the public API diff and the
  import graph (the TypeScript adapter also reads JavaScript). A **tool adapter** records what its
  tool needs (installed dependencies, a build) and whether it installs
  them itself; the review never builds or installs, so a tool that would
  is not used and its detector's heuristic runs instead.
- **Signal**: a detector's note that a file changed in a way worth a look
  (added, renamed, a changed public symbol). Not a finding: a judgment step
  decides whether it is one.
- **Bucket**: where the brief puts a changed file, exactly one each, by
  fixed rules in this order: **must-read** (a finding asks for it),
  **unproven** (no content detector covered its type: read it),
  **glance** (a signal, a finding or a risk zone, with the reason),
  **skim** (every applicable content detector covered it and found
  nothing; the proof names them).
- **Repo facts**: what `review-setup` records about a repository in
  `docs/agents/review.md`, committed: its stacks and its risk map. Never a
  tool version or the run root, which belong to the machine.
- **Risk map**: the repository's path globs (gitignore-like) mapped to risk
  zones. `review-pr` reads the copy committed at the base, so a branch
  can't narrow its own.
- **Risk zone**: a kind of change the reviewer wants to see whatever the
  detectors say: `auth`, `personal-data`, `payments`, `concurrency`,
  `irreversible`, `public-api`, or one the repository names. A changed file
  in a zone is never `skim`, and its bucket names the zone.
- **Attention**: a review finding's claim on the reviewer, `must-read` or
  `glance`. A finding can move a file up; nothing but detector evidence
  makes it `skim`.
- **Reviewer question**: the question a review finding asks the reviewer to
  answer at its location.
- **Brief**: the projection of a run (its header, detector outputs and
  findings) the reviewer reads: declared against detected risk, the
  buckets, the coverage gaps and the proposed verdict. Regenerated, never
  edited.
- **Verdict**: the brief's proposal, `merge`, `fix` or
  `close-and-reprompt`, always with the dimensions that did not run. The
  reviewer decides.
- **Round**: the number of distinct heads reviewed on one branch. The third
  with a merge-blocking finding proposes `close-and-reprompt`.
- **Sources**: what a change was supposed to do, as a run found and read
  it: the PR body, the spec and its tickets. The tickets the PR closes are
  **in scope**; the spec's other tickets are **siblings**.
- **Pocock contract**: the artifacts the review reads from Matt Pocock's
  skills (tracker doc, domain doc, spec, tickets, PR body), the sections it
  relies on in each, and the upstream commit last checked. Each artifact
  is checked when it is read.
- **Contract drift**: an artifact that lacks a section the contract relies
  on, such as a ticket whose `Acceptance criteria` heading was renamed. The
  dimension it feeds becomes `not-evaluable (contract drift: ...)`, and the
  run goes on. Absent is not drift: a PR body without `Merge Danger` is
  **not declared**.
- **Intent**: whether a change does what its tickets asked, judged by the
  intent step: each acceptance criterion (`#41 AC2`) found in the hunks,
  partly found or not found; each changed file justified by a criterion, a
  ticket or the spec, or **out of scope**; no change against the spec's
  Implementation Decisions or Out of Scope. **Misread intent** (more than
  half of the criteria not found, a file out of scope, a decision broken)
  proposes `close-and-reprompt`.
- **Worksheet**: the findings file `run.py` writes for a judgment step,
  with every row the step must fill and `?` where it judges, so that no
  criterion, file, signal, dependency or term can be left out.
- **Contracts**: what a change breaks outside the diff, judged by the
  contracts step from the detectors' signals and the code: each signal is
  **one-way** (reverting the merge does not undo it: data dropped, a
  contract external consumers rely on), **breaking** (a consumer outside
  the diff breaks, and a revert undoes it) or **minor**.
- **Door**: the risk a PR body declares under `Merge Danger`, one-way or
  two-way, compared mechanically with the Door the contracts step
  detects. A difference is a **disagreement** finding, at the top of the
  brief. The **Blast Radius** word is never compared: the brief shows it
  beside the detected risk zones and fan-in.
- **Fan-in**: the references to a changed public symbol outside the diff,
  counted by a word search and labelled heuristic.
- **Structure**: the new shape a change gives the codebase, judged by the
  structure step: new files by **class** (`module`, `layer`, `entry
  point`, `migration`, `config`, `test`), new dependencies **needed** or
  **not needed**, new type names that are **domain terms** the glossary
  lacks, new imports between modules that **fit** or cross a
  **boundary**, a **pattern divergence** (a second way of doing what the
  codebase already does) and a change against an ADR or a decision no ADR
  records.
- **Import graph**: the file-level imports of each side of a change,
  mapped to modules, which a stack adapter supplies in one stack-neutral
  format. The review computes the new cross-module edges and the new
  cycles from it. Without an adapter, the import graph is not evaluable.
- **Dimension**: one part of a full review: the judgment steps (intent,
  contracts, structure) and the later gates, test integrity and
  adversarial review. One not run is a coverage gap, stated in the verdict.
