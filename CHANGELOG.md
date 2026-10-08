# Changelog

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
