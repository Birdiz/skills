# Changelog

## 0.11.0 (unreleased)

Three dynamic axes, in the same form (skill plus `areas.md`); none has run
yet.

- Add `accessibility`: a sample of pages (main flows, one per template), an
  automated pass whose results are leads, then the keyboard, the
  accessibility tree, forms and visual checks by hand, each problem traced to
  its template. WCAG or RGAA from the profile; a legal obligation is the
  owner's to state, and raises one level
- Add `seo`: a rate-limited crawl, robots and sitemaps against it, served
  against rendered HTML, routes no link reaches. Rated for the documented
  production configuration; which pages should be indexed is the owner's
  intent, proposed from the map and asked up front
- Add `performance`: server work per request read in the code, single-request
  measurements and Lighthouse medians, growth with data. A measurement
  stands alone only on a production-like configuration; expected volumes are
  asked up front
- Rules of engagement: signing in with an account the auditor provides is
  ordinary use; forms are submitted only to show validation (passive) or on
  the auditor's own data (active); crawls are sequential, one request per
  second at most, capped; no load or stress test in any regime

## 0.10.0 (unreleased)

From the 0.9.0 rerun of `code-quality` and `architecture` (fresh copy of the
gn-platform workspace, then `verify-findings`): 7 findings, 7 confirmed, no
rating changed, text corrected in 6. The 0.9.0 rules held: `L-SEC-21` closed
as settled, the performance lead moved, the engagement file untouched, the
same problems found. New: a shell hook truncated `git log` and `grep` output
without saying so; an identical lockfile sat over an incomplete install; the
two grids rated the same race differently; the two axes diverged on a
weakness the owner documents as planned work.

- Rules of engagement: counts and lists cited as evidence come from a script
  run with `bash`; an install is used only if its record of installed
  packages lists every locked one; a map without `dependencies:` leaves the
  search to the step, recorded; tool runs go in `tool-output/<step>/`; a
  pinned base image may carry a tool without its own image; another clone's
  graph index at the same commit may be queried, and said
- `finding-format`: the rare-precondition and planned-change moves apply to
  every grid; a weakness the owner documents as a known limit or planned
  work is still a finding, citing the document, level kept; partial
  settlement (`settles L-… (part: …)`); `references` may be empty; questions
  may concern a coverage area and go in the file at once when asked up
  front; area names and status words stay in English
- `verify-findings`: looks for the owner's known limits and planned work;
  corrects a fixed fact where the coverage repeats it, annotates questions
  the repository answers; rewrites partially settled leads
- `code-quality`: the CI question goes in a new findings file first; fix
  commits by subject with the exact command; under three months, review
  rounds are one change and a hotspot only supports a finding; grid row for
  what misleads a reader replaces the hygiene row; only copies whose
  behaviour differs are diverged
- `architecture`: "structural Unknown" defined, leads closed before
  finishing, those already another axis's finding closed with its ID; leads
  to any other axis, in-plan ones included; a deliberate layout is a force;
  "most main flows" is more than half
- `recon`: an existing install is checked for completeness, not only its
  lockfile

## 0.9.0 (unreleased)

From the first run of `code-quality` and `architecture` (gn-platform, same
commit and map as the first engagement, axes in parallel sub-agents, then
`verify-findings`): 8 findings, 8 confirmed, no rating changed, text
corrected in 4. Twice a new axis settled an open `app-security` lead that
stayed open in its file; a performance lead was closed instead of moved; two
reasons for a severity move were wrong while the move held; both axes wrote
the engagement file at the same time.

- `finding-format`: one problem stays in one axis. A consequence for another
  axis is appended there as a lead, even outside the plan; a finding that
  settles another axis's lead names it; findings with one cause cite each
  other. What was examined and dropped is a coverage note, not a lead
- `finding-format`: pointers quote a few words of their line; "shown" means
  every step pointed, one reasoned step caps confidence at medium; a severity
  move gives its reason with a pointer; a system not yet in production is
  rated for its documented deployment; `evidence_regime` defined
- `verify-findings`: closes the leads that confirmed findings settle, in
  their own file; checks the reason of a severity move, not only the move;
  moves a lead closed although it belonged to another axis; a cost the audit
  itself met counts when any newcomer would meet it
- Rules of engagement: a tool an axis names runs from a pinned image when the
  profile lists `docker`; read-only host commands are allowed; dependency
  code is read where the map says, lockfile rechecked; rules and scripts
  written for a run are kept; each step lists its tools in its own output
  and only `audit-kickoff` writes them to the engagement file
- `code-quality`: CI merge-blocking asked up front; whole history when
  shorter than twelve months, merges excluded, fix commits by subject; under
  three months, a hotspot needs reworked code; grid read where the wrong
  result reaches a user, a rare precondition lowers one level
- `architecture`: the map's departures and structural unknowns become leads
  first; coarse modules split and said; coupling without merges, three
  commits or more, supporting only under three months of history; grid row
  for gaps that delay diagnosis or a decision; an unnoticed failure is an
  outage of what it carries; plans in the repository count for raising a
  level
- `recon`: `tools:` in the map header. `audit-setup`: detects `docker` as the
  way to run named tools

## 0.8.0 (unreleased)

Rewritten for brevity, following mattpocock/skills `writing-for-agents`. No
behaviour change intended; file formats unchanged. 7 678 words to about
4 950, sibling files included; the rest is mostly file templates, kept as
they are.

- History and justifications moved out of the skills (this file and the ADRs
  keep them); each rule stated once, in the affirmative
- Reference moved to sibling files reached by a link:
  `audit-kickoff/engagement-template.md` (template, workspace, capability
  matrix), `finding-format/schema.md` (finding layout, IDs, lead bullet,
  severity scale), `app-security/areas.md` (areas, severity grid),
  `audit-report/deliverables.md` (peer report, summary, prompts)
- `finding-format/rules-of-engagement.md`: the single home of what an audit
  may touch and run (read-only repository, no execution, passive and active
  regimes, secrets, scripted tool runs, excluded artifacts), formerly spread
  across `recon`, `app-security` and `verify-findings`
- `audit-setup`, `audit-kickoff`: interviews in rounds over the frontier, at
  most three questions each; the question table becomes a field-to-reader
  line in the engagement template
- `finding-format` description names the rules of engagement, so steps that
  need them reach the skill
- Leading words: rules of engagement, projection, refute, blocker, draft

Regression on the first engagement (same post-recon input, `app-security`
run with 0.8.0 and with 0.7.0 as a control): both versions find the same
seven weaknesses and miss the same ones; verification, an auditor answer,
the draft and revision loop behave as before. Fixes from the run:

- The secret rule is stated in the rules of engagement for every workspace
  file, default and placeholder values included, and recalled where
  findings are written; with the rule behind a link only, a run quoted a
  secret
- `finding-format`: the framework text is fetched into `tool-output/` before
  a reference is cited
- `app-security`: the passive regime is recalled where the running target is
  handled; behind a link only, a run requested a path it had composed. Every
  cited identifier, CWE included, comes from the framework text

New axes, written in the same form (skill plus `areas.md` with the areas and
the severity grid); neither has run on a real codebase yet:

- Add `code-quality`: defects on the main flows, error handling, hotspots
  from history and complexity, duplication, tests read but not run,
  consistency with the project's own rules. A finding names a cost shown in
  this codebase, never a preference
- Add `architecture`: real dependency graph against the documented one,
  change coupling from history, data ownership, consistency and failure
  between components, third-party coupling, operability. Judged against the
  system's forces, never against a style; fixes needing a decision are not
  promptable
- Rules of engagement: an analyser whose project configuration is code runs
  only with a configuration the auditor wrote; `git log` commands are
  scripted like scanner runs
- `verify-findings`: for these two axes, refute a claimed cost that is a
  preference
- `audit-setup`: detect `lizard`, `scc` and `jscpd`

## 0.7.0 (unreleased)

- Ship as a Claude Code plugin (`birdiz-skills`) through a marketplace in
  this repository

From the second report run: the draft mechanism worked (ten discrepancies
down to four, accepted findings in their own section, skill versions
checked), but kept the report in draft over cosmetic issues and over a rule
that could not be satisfied.

- `audit-report`: discrepancies are blocking (what a reader acts on is wrong
  or unreadable) or cosmetic (form only); only blocking ones keep a
  deliverable in draft
- `finding-format`: leads of an axis outside the plan carry `open: axis not
  requested`; answer labels stay in English; an answer can change
  `promptable`
- `recon`: same status for leads outside the plan, written in the engagement
  language

## 0.6.0 (unreleased)

From the first report run. The report listed ten discrepancies between the
findings and their verification notes, written before 0.4.0, and the owner's
answers had changed two findings with no rule for it.

- `finding-format`: new `resolution` key (`open`, `accepted`, `fixed`),
  independent of `status`; quick wins require `open`. How a session records
  an auditor's answer and applies its consequences
- `verify-findings`: revision mode, to apply listed discrepancies to findings
  already verified
- `audit-report`: consistency check before writing; deliverables marked DRAFT
  while discrepancies remain, then handed to `verify-findings` and
  regenerated; accepted findings in their own section; skill versions
  actually used in the provenance

## 0.5.0 (unreleased)

- Add `audit-report`: peer report, plain-language summary and remediation
  prompts, chosen from the engagement's audience. A projection of the
  findings: no new analysis, counts recomputed, stops when verification is
  missing. Sensitive findings reach the summary by consequence only; prompts
  describe the target state and never the attack
- `audit-kickoff` and `verify-findings` hand over to `audit-report`

## 0.4.0 (unreleased)

From the first verification run (11 findings: 11 confirmed, 0 refuted, 10
corrected).

- `verify-findings`: corrects in place what it proved wrong, quoting the old
  text in its note, so reports never carry a known error; a rating change
  must give its reason and update every sentence stating the old rating;
  passive means no guessed URLs or identifiers
- `finding-format`: `sensitive` asks whether the finding helps an outside
  attacker; weaknesses only a legitimate privileged user can exercise are not
  sensitive. A reference must state what the finding says is missing; a
  versioned URL is enough. Old keys (`impact`) are ignored
- `app-security`: guessed identifiers are not passive

## 0.3.0 (unreleased)

- Add `verify-findings`: the only step that confirms or refutes a finding,
  run in a context that did not write it, trying to refute rather than
  confirm. Adds a `verification` key and paragraph to every finding,
  spot-checks closed leads, writes no new findings
- `audit-kickoff`: runs `verify-findings` after the axes, or tells the
  auditor to open a new session when there are no sub-agents
- `finding-format`: status changes belong to `verify-findings`

## 0.2.0 (unreleased)

From the first real engagement (a self-audit, `app-security` only).

- Every skill carries a `Version:` line, so an engagement records which
  version produced it even when installed without this repository
- `finding-format`: remove `impact` (it duplicated severity); quick win is now
  confirmed, severity medium or above, effort S. Leads get IDs and a check,
  and the owning axis closes each one. New coverage status `not-requested`.
  New section for questions to the auditor. English headings and keys, prose
  in the engagement language. Cite only what a reader can open; check
  framework references against their source. Publicly observable findings
  are not sensitive
- `recon`: graph edges can be wrong and are verified; dependency source from
  an identical install or an install without scripts; unknowns say who can
  settle them; leads stay short; leads for axes outside the plan are kept
- `app-security`: severity grid recalibrated, with an availability row;
  scanner runs scripted and kept; the auditor's own artifacts excluded from
  scans; owner instructions for agents are not injection; running target
  checked against the audited commit; every lead closed
- `app-security`: align the `sensitive` rule and dependency reading with
  `finding-format` and `recon`
- `audit-kickoff`: records the working copy and what the running target
  serves; end report lists the questions for the auditor

## 0.1.0 (unreleased)

- Add `audit-setup`, `audit-kickoff`, `finding-format`, `recon`
- Add `app-security`, the first audit axis
- `audit-kickoff`: ask questions in batches of up to three; record the
  auditor's own authorization for targets they own; never confirm an
  engagement with authorization pending; list excluded MCP servers
- `audit-kickoff`: after confirmation, run `recon` and the planned axes
  without asking again; stop only for blockers, not for missing optional
  tools
- `audit-setup`: ask questions in batches
- `app-security`: a running target provided by the auditor is not
  "executing the project"; active tests limited to authorized hosts
- Add glossary (`CONTEXT.md`) and ADRs 0001 to 0003
