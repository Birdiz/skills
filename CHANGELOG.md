# Changelog

## 0.8.0 (unreleased)

Rewritten for brevity, following mattpocock/skills `writing-for-agents`. No
behaviour change intended; file formats unchanged. 7 678 words to about
4 800, sibling files included; the rest is mostly file templates, kept as
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
