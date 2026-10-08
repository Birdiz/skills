---
name: finding-format
description: Schema and rules for audit findings, leads, coverage and the rules of engagement (evidence, severity, sensitivity, passive or active testing). Use whenever writing, reviewing or reading findings in an audit workspace, and before any audit report.
---

# finding-format

Version: 0.8.0 (audit skills, see CHANGELOG)

A finding is written once, in one schema, whatever the axis; reports are
projections of it. Layout, IDs, lead bullet, severity scale:
[schema.md](schema.md). What an audit may touch and run:
[rules-of-engagement.md](rules-of-engagement.md).

Findings live in `<workspace>/findings/<axis>.md`, one file per axis
(including axes outside the plan that received leads), sections `## Coverage`,
`## Findings`, `## Leads`, then `## Questions for the auditor` if needed.
Headings, bold labels, YAML keys and values stay in English for the parsers;
titles and prose use the engagement's `language`.

## Evidence

- **No evidence, no finding.** A suspicion is a lead, and a lead never reaches
  a report as a finding: nothing downstream catches a wrong finding.
- **Reproducible**: a reader with the same access sees the same thing (file
  and line, command and output, URL and response).
- **Openable**: cite only the audited repository, the workspace,
  `tool-output/`, or a public reference; never memory or a past conversation.
- **References from the source**: copy the identifier (ASVS, WCAG, CWE) from
  the framework text, citing the one or two whose requirement states what is
  missing; keep the copy in `tool-output/` or give a versioned URL, and name
  the version.
- **A missing edge or an empty search proves nothing**: injection,
  subscribers, config routing, reflection and templates hide calls; dead code
  or a missing check needs the code read.
- **Confidence rates the finding, severity the consequence**: a critical with
  low confidence stays critical, and says so.
- **`status` starts `unverified`**; only `verify-findings` sets `confirmed` or
  `refuted`, and refuted findings stay. Legacy keys (`impact`) are ignored.

## Fields

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
- **Quick win**, derived and never stored: `confirmed`, `open`, medium or
  above, effort S.

## Leads

Recon or any axis writes them; the owning axis closes each before finishing:
rewriting the bullet's status as `promoted to F-…`, `closed: <why, pointer>`,
or `open: <what settles it, and who: agent, auditor or owner>`. Leads of an
axis outside the plan carry `open: axis not requested` until that axis runs.

## Questions and answers

One question per line, for what only the auditor or owner can settle, with the
lead or finding concerned. An answer is recorded under the question
(`**Answer (YYYY-MM-DD):**`) and in the finding as `**Auditor answer.**` after
`**Verification.**`. A change it brings (rating, remediation, `promptable`,
`resolution: accepted`) is applied in place with its reason, as
`verify-findings` does. `status` stays with verification; an unshown claim
becomes a lead.

## Coverage

Per area: `evaluated`, `partial` (gap stated), `not-evaluable` (missing
capability named, no findings), `not-requested`, the last two kept distinct.
Name the evidence sources: audited commit, dependency code origin, running
target with its commit and environment. For a target on another commit,
compare the two: dynamic evidence covers only what the difference leaves
untouched, and the coverage says so.
