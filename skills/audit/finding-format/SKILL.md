---
name: finding-format
description: Schema and rules for audit findings, leads, coverage and the rules of engagement (evidence, severity, sensitivity, passive or active testing). Use whenever writing, reviewing or reading findings in an audit workspace, and before any audit report.
---

# finding-format

Version: 0.11.0 (audit skills, see CHANGELOG)

A finding is written once, in one schema, whatever the axis; reports are
projections of it. Layout, IDs, lead bullet, severity scale:
[schema.md](schema.md). What an audit may touch and run:
[rules-of-engagement.md](rules-of-engagement.md).

Findings live in `<workspace>/findings/<axis>.md`, one file per axis
(including axes outside the plan that received leads), sections `## Coverage`,
`## Findings`, `## Leads`, then `## Questions for the auditor` if needed.
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
  when the running target was needed, `declarative` when the finding rests on
  an answer from the owner.
- **`sensitive: true`** when a leak would help an outsider attack, or exposes
  personal data: exploitable vulnerabilities, where a secret is, non-obvious
  weaknesses reachable from outside, personal data in evidence. `false` for
  what any visitor sees, what only a legitimate privileged user can do,
  hygiene, documented framework defaults. Sensitive findings appear only in
  the confidential report.
- **`promptable: true`** when a coding agent could apply the fix in the code;
  human actions (rotate a key, sign, change DNS, record a decision) are `false`.
- **`resolution`**, independent of `status`: `open` (default), `accepted`
  (owner keeps it; `**Auditor answer.**` with date and decision), `fixed`
  (verified at a later commit).
- **`references`** may be empty when no framework names the problem; a
  reference is never stretched to fill it.
- **Quick win**, derived and never stored: `confirmed`, `open`, medium or
  above, effort S.

## Leads

Recon or any axis writes them; the owning axis closes each before finishing:
rewriting the bullet's status as `promoted to F-…`, `closed: <why, pointer>`,
or `open: <what settles it, and who: agent, auditor or owner>`. Leads of an
axis outside the plan carry `open: axis not requested` until that axis runs.

Across axes, one problem stays in one axis:

- A consequence that belongs to another axis (security, performance...)
  becomes a lead in that axis's file, created if absent, appended as one
  bullet with the file re-read just before (axes may run in parallel);
  outside the plan it carries `open: axis not requested`. Nothing else in
  another axis's file is edited.
- A finding that settles another axis's lead names it in its evidence
  (`settles L-SEC-21`, or `settles L-SEC-06 (part: <which>)` for part of
  it); `verify-findings` rewrites that lead.
- Findings with one cause cite each other in their technical explanation.

What was examined and dropped (harmless, or no cost shown) is a note in the
area's coverage, not a lead: a lead is what remains suspected.

## Questions and answers

One question per line, for what only the auditor or owner can settle, with the
lead, finding or coverage area concerned. A question needed before the work
(one the skill asks up front) goes in the file at once, created for it.

An answer is recorded under the question (`**Answer (YYYY-MM-DD):**`) and in
the finding as `**Auditor answer.**` after `**Verification.**`. A change it
brings (rating, remediation, `promptable`, `resolution: accepted`) is applied
in place with its reason, as `verify-findings` does. `status` stays with
verification; an unshown claim becomes a lead.

## Coverage

Per area: `evaluated`, `partial` (gap stated), `not-evaluable` (missing
capability named, no findings), `not-requested`, the last two kept distinct.
Name the evidence sources: audited commit, dependency code origin, running
target with its commit and environment. For a target on another commit,
compare the two: dynamic evidence covers only what the difference leaves
untouched, and the coverage says so.
