---
name: finding-format
description: Schema and rules for audit findings, leads, coverage and the rules of engagement (evidence, severity, sensitivity, passive or active testing). Use whenever writing, reviewing or reading findings in an audit workspace, and before any audit report.
---

# finding-format

Version: 0.16.0 (audit skills, see CHANGELOG)

A finding is written once, in one schema, whatever the axis; reports are
projections of it. Layout, IDs, lead bullet, severity scale:
[schema.md](schema.md). What an audit may touch and run:
[rules-of-engagement.md](rules-of-engagement.md).

Findings live in `<workspace>/findings/<axis>.md`, one file per axis
(including axes outside the plan that received leads), sections `## Coverage`,
`## Findings`, `## Leads`, then if needed `## Leads for other axes`, `##
Questions for the auditor` (the owner's included) and `## Created on target`.
Recon may have created the file with leads and placeholders: the axis keeps
the leads and replaces the rest.
Headings, bold labels, YAML keys and values, area names and status words
(`evaluated`, `open:`, `closed:`) stay in English for the parsers; titles and
prose use the engagement's `language`.

## Evidence

- **No evidence, no finding.** A suspicion is a lead, and a lead never reaches
  a report as a finding: nothing downstream catches a wrong finding.
- **Reproducible**: a reader with the same access sees the same thing (file
  and line, command and output, URL and response).
- **Quoted**: each pointer carries a few words of the line it points to
  (`src/Entity/User.php:42` "`strtolower($email)`"), so a drifted line shows
  without opening the file; a line holding a secret is quoted up to the
  secret.
- **Shown** means every step is pointed: code, dependency code, history or
  tool output. When one step is only reasoned (an interleaving of two
  requests, a state nobody reached) and every other is pointed, the finding
  stands with confidence at most medium.
- **Openable**: cite only the audited repository, the workspace,
  `tool-output/`, or a public reference; never memory or a past conversation.
- **References from the source**: copy every identifier (ASVS, WCAG, CWE
  alike) from the framework text, kept in `tool-output/` (fetched when absent) or behind a
  versioned URL, version named; cite the one or two whose requirement states
  what is missing.
- **A missing edge or an empty search proves nothing**: injection,
  subscribers, config routing, reflection and templates hide calls; dead code
  or a missing check needs the code read.
- **A secret is recorded by location**: file, line, kind, presence in
  history; its value is `<redacted>`, evidence and questions included (rules
  of engagement).
- **An answer is evidence of what the owner states.** A declarative
  finding quotes the answer with its question ID and date (`Q-PRI-03,
  answer 2026-10-11: "…"`), and joins it to what the repository or target
  shows wherever they can. An answer that reveals a gap is enough for a
  finding; one that claims a control or a fact the audit cannot observe
  settles no finding and closes a lead only as declared (Leads). An
  observation (repository, target, forge or cloud settings) wins over an
  answer that contradicts it: the question is asked again once, with the
  observation, and both answers and the contradiction are stated. A document
  the owner gives (a record, a contract) is copied into
  `<workspace>/client-docs/`, secrets and personal data masked, and cited
  there.
- **Confidence rates the finding, severity the consequence**: a critical with
  low confidence stays critical, and says so.
- **`status` starts `unverified`**; only `verify-findings` sets `confirmed` or
  `refuted`, and refuted findings stay. Legacy keys (`impact`) are ignored.

## Rating

- The axis grid gives the starting level, for a precondition met in
  ordinary use. A rare one (a narrow window, an unusual sequence of
  administrative actions) lowers one level; a change the problem blocks,
  planned by the owner (an answer, or the repository's own plans), raises
  one. Every move states its reason with a pointer in the technical
  explanation, so the verifier can check the reason and not only the move.
- A weakness the owner already documents as a known limit or planned work is
  still a finding: it exists at the audited commit. It cites that document
  and keeps its level; only an owner's answer makes it `accepted`.
- A system not yet in production is rated for the deployment its owner
  documents, and the finding says so: its absence lowers nothing, or the
  rating would be wrong on launch day.

## Fields

- **`evidence_regime`**: `static` when the repository is enough, `dynamic`
  when something running was observed (the target, or forge and cloud
  settings read within the engagement's scope), `declarative` when the
  finding rests on an answer from the owner.
- **`locations`**: `path:line` where there is one; otherwise what a reader
  opens: `forge: <setting>`, `answer: Q-…`, or the directory an absence was
  searched in.
- **`sensitive: true`** when a leak would help an outsider attack, or exposes
  personal data: exploitable vulnerabilities, where a secret is, non-obvious
  weaknesses reachable from outside, what lets an outsider learn about a
  given account (its existence, its state), personal data in evidence.
  `false` for what any visitor sees and that targets no one (a missing
  header), what only a legitimate privileged user can do,
  hygiene, documented framework defaults. These cases win over an axis's
  default (a fallback secret's location is sensitive in every axis).
  Sensitive findings appear only in the confidential report.
- **`promptable: true`** when a coding agent could apply the fix in the code;
  human actions (rotate a key, sign, change DNS, record a decision) are `false`.
- **`resolution`**, independent of `status`: `open` (default), `accepted`
  (owner keeps it; `**Auditor answer.**` with date and decision), `fixed`
  (verified at a later commit).
- **`references`** may be empty when no framework names the problem; a
  reference is never stretched to fill it.
- **Quick win** is a property of a fix, derived (`remediation-plan`): a
  finding is one through its fix.

## Leads

Recon writes them in every axis file before the axes run; then each axis
writes only in its own file. The owning axis closes each lead before
finishing, rewriting its status as one of:

- `promoted to F-…`;
- `closed: settled by F-…`, by a finding of any axis that covers it;
- `closed: <why, pointer>`;
- `closed: intended (Q-…), <pointer>`, for behaviour the code shows and the
  owner's answer says is wanted;
- `closed: declared by owner (Q-…), not observed`, whenever the closure
  rests on an answer the audit cannot check (a control, a fact about a
  future deployment); reports list these apart;
- `open: <what settles it, and who: agent, auditor or owner>`;
- a lead settled in part joins the forms above with `;`: `open: <part>
  settled by F-…; remains <what>, <who>`, or `closed: <part> settled by
  F-…; rest declared by owner (Q-…), not observed`.

The new status replaces the old one.

Leads of an axis outside the plan carry `open: axis not requested` until
that axis runs.

Across axes, one problem stays in one axis, and no axis edits another's file
(axes run in parallel, and a file rewritten from an older read loses what
another step added):

- A consequence that belongs to another axis goes under `## Leads for other
  axes` in the writer's own file, one bullet each, `- **<target axis>:
  <title>.** <observation, pointers, check>`, with no ID. `verify-findings`
  moves them into the target files with the next free ID and the status
  `open: moved from <file>; <who settles it>`.
- A finding that settles another axis's lead names it in its evidence
  (`settles L-SEC-21`, or `settles L-SEC-06 (part: <which>)`);
  `verify-findings` rewrites that lead.
- Findings with one cause (one fix removes both) cite each other in their
  technical explanation.
- A lead moved into the file of an axis that has already run, or an answer
  recorded under one of its questions, is taken up by a **lead pass** of
  that axis (below).

What was examined and dropped (harmless, or no cost shown) is a note in the
area's coverage, not a lead: a lead is what remains suspected.

### Lead pass

The axis takes up, after it ran, the leads moved into its file and the
answers to its questions, with the method of its skill where a lead needs
it. It may:

- close or promote its open leads, as above;
- apply the answers (Questions and answers), and write the findings an
  answer reveals, on a coverage area as on a lead;
- open leads, ask questions, write `## Leads for other axes` and `## Created
  on target`;
- update the coverage of the areas it touched, and add one dated line:
  `lead pass <YYYY-MM-DD>: skill: <name>@<version>, tools: [...]`.

Everything else in the file stays as written: other areas, findings no
answer concerns, earlier provenance. Its findings and the confirmed findings
it changed then go through verification. A lead or question it opens waits
for the next run: `audit-kickoff` does one round.

## Questions and answers

One bullet per question, `Q-<AXIS>-<NN>`, for what only the auditor or owner
can settle, with the lead, finding or coverage area concerned, and the
**proposal**: the answer the repository suggests, with its pointer. A fact
only the owner knows (MFA, volumes, contracts) has no proposal: the question
is asked open, and no step invents one. A question asked in another file is
not asked again: refer to its ID, and ask only what it leaves. A question
the skill asks up front goes in the file before any finding is written,
created for it if absent. Questions written without an ID (older skills) are
numbered by the next step that writes the file, in order, text unchanged.

An axis that cannot reach the owner (a sub-agent, an absent client) works
on: it rates on what is shown, and a finding whose rating depends on an
answer says which answer moves it, and how.

An answer is recorded under the question by whoever receives it, while no
step is writing that file: `**Answer (YYYY-MM-DD, who):** "<the owner's
words>"`, then, when the owner chose a proposal, `accepts the proposal:
<proposal>`, so the owner's words and the recorder's stay apart. A question
asked and left unanswered gets `**Asked (YYYY-MM-DD), not answered.**`.

The axis's lead pass applies the answers. In a finding the answer changes,
or whose question names it, as `**Auditor answer.**` after
`**Verification.**`: the change (severity, confidence, references,
remediation, `promptable`, `resolution: accepted`, any sentence stating the
old value) applied in place, old text quoted, with its reason. An answer
that changes nothing is one line in the coverage, not a paragraph per
finding. In a lead: closed, promoted or kept open. An answer describing a
practice (a habit, a manual step) is not a decision to keep a risk:
`accepted` needs the owner to say so. `status` stays with verification; an
unshown claim becomes a lead.

## Coverage

Per area: `evaluated`, `partial` (gap stated), `not-evaluable` (missing
capability named, no findings), `not-requested`, the last two kept distinct.
An area judged on answers names them, and lists the controls it takes as
`declared, not observed (Q-…)`; one waiting for an answer that could change
a finding or a rating in it, or promote a lead to a finding, is `partial`,
whether the question was asked or not. An answer that defers to someone
else (counsel) leaves nothing waiting in the area: the deferred point is a
lead or a condition stated in a finding.
The axis as a whole is `evaluated` when every area is, `partial` with the
partial areas named, `not-evaluable` when a required capability was missing.
The coverage opens with the skill that wrote it (`skill: <name>@<version>`)
and the tools it ran; each later pass adds its own line (Lead pass).
Name the evidence sources: audited commit, dependency code origin, running
target with its commit and environment. For a target on another commit,
compare the two: dynamic evidence covers only what the difference leaves
untouched, and the coverage says so.
