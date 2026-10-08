---
name: finding-format
description: The schema and rules every audit finding must follow (evidence, severity, confidence, effort, sensitivity). Use whenever writing, reviewing, or reading findings in an audit workspace, and before producing any audit report.
---

# finding-format

Version: 0.7.0 (audit skills, see CHANGELOG)

One schema for every finding, whatever the axis. Reports are projections of
the same findings, so a finding is written once and never re-authored per
deliverable.

## Where findings live

`<workspace>/findings/<axis>.md`, one file per axis, including axes outside
the plan when leads were noted for them. Each file has these sections, in
this order:

1. `## Coverage` (what was and was not evaluated)
2. `## Findings`
3. `## Leads` (suspicions without evidence, and what became of them)
4. `## Questions for the auditor` (only if some answer is needed)

## Language

Section headings, the bold labels inside a finding and every YAML key and
value stay in English: they are the contract other skills and scripts parse.
Titles and prose are written in the engagement's `language`.

## A finding

A level-3 heading, a YAML block, then four prose sections.

````markdown
### F-SEC-003 Session cookie set without Secure flag

```yaml
id: F-SEC-003
axis: app-security
status: unverified        # unverified | confirmed | refuted
severity: medium          # critical | high | medium | low | info
confidence: high          # high | medium | low
evidence_regime: static   # static | dynamic | declarative
effort: S                 # S (hours) | M (days) | L (weeks)
resolution: open          # open | accepted | fixed
sensitive: false
promptable: true
locations:
  - config/packages/framework.yaml:14
commit: a1b2c3d
references:
  - OWASP ASVS 5.0 3.3.1
```

**Evidence.** What was observed, with enough detail to reproduce: file and
line, the command run and its output, or the URL and the response.

**Technical explanation.** For a peer: cause, consequence, conditions. If the
severity departs from the axis grid, say from what and why.

**Plain-language explanation.** For a non-technical reader: what could go
wrong and why it matters to the business. No jargon, no exploit detail.

**Remediation.** The fix, and how to check it worked.
````

### IDs

`F-<AXIS>-<NNN>` for findings, `L-<AXIS>-<NN>` for leads, never reused, never
renumbered. Axis codes: `QUA` code quality, `ARC` architecture, `SEC` app
security, `INF` infra security, `PRI` privacy, `A11Y` accessibility, `SEO`,
`PERF` performance.

## Rules

**No evidence, no finding.** Something suspected but not shown goes under
`## Leads`. Leads never reach a report as findings. Reason: nothing downstream
catches a wrong finding, and a plausible false positive costs the client real
work and the auditor credibility.

**Evidence must be reproducible by someone else.** A reader with the same
access must be able to see the same thing. "The code seems to" is a lead.

**Cite only what a reader can open.** The audited repository, the workspace,
tool output saved in `tool-output/`, a public reference. Never the agent's
memory, a previous conversation or a project note the reader does not have.

**References are checked against their source.** A framework identifier (ASVS,
WCAG, CWE) is copied from the framework text, not recalled, and the
requirement it names must state what the finding says is missing, not merely
exist in the same chapter. Cite the one or two most specific. Keep the copy
used in `tool-output/` or give a versioned URL, and name the version.

**Absence in a graph or a search is not proof.** Dependency injection, event
subscribers, config-driven routing and templates hide edges. Claims of dead
code or missing checks need the code read, not only a query.

**Never quote a secret.** Record where it is and what kind it is. Redact the
value, in every file, including evidence.

**Confidence is about the finding, severity about the consequence.** A
critical finding with low confidence stays critical and says so.

**Status starts at `unverified`.** Only `verify-findings`, run by a context
that did not produce the finding, may set `confirmed` or `refuted`. It adds a
`verification` key and a `**Verification.**` paragraph, and corrects in place
what it proved wrong. Keys from older versions of this schema (`impact`) are
ignored. Refuted findings stay
in the file, marked, so the same false positive is not rediscovered.

### `sensitive`

The test: would this finding, if leaked, help someone **outside** the
organization attack it, or expose personal data?

- `true`: exploitable vulnerabilities, where a secret is, weaknesses reachable
  from outside that are not obvious, any personal data in the evidence.
- `false`: what any visitor can already observe (a missing response header, a
  public version banner); weaknesses only a legitimate privileged user can
  exercise (missing traceability of an admin action); pure hygiene; a
  framework's documented default behaviour.

Sensitive findings appear only in the confidential report.

### `promptable`

`true` only when a coding agent could apply the remediation in the codebase.
`false` for human actions: rotating a key, signing a processor agreement,
enabling MFA, changing a DNS record, recording a decision.

### `resolution`

What the owner did about the finding. Independent of `status`, which says
whether the finding is true.

- `open` (default, may be omitted): nothing decided.
- `accepted`: the owner decided to keep the behaviour or the risk. Requires an
  `**Auditor answer.**` paragraph with the date and the decision.
- `fixed`: only set by verifying the fix at a later commit, never on the
  owner's word.

### Quick win

Derived, never stored: `status: confirmed`, `resolution: open`, severity
`medium` or above, and `effort: S`.

## Default severity scale

| Level | Meaning |
|---|---|
| critical | Exploitable now, or legal exposure now; data loss, takeover, or outage |
| high | Serious consequence, needs a realistic precondition |
| medium | Real weakness, limited consequence or hard to reach |
| low | Hygiene; raises cost or risk over time |
| info | Observation, no action required |

A custom scale from the auditor profile replaces the meanings, not the number
of levels. Axes may give a more specific grid; it must map onto these levels.

## Leads

One bullet each, with pointers and the check that would settle it:

```markdown
- **L-SEC-04 Consent written outside the lifecycle.** Controller saves the
  flag directly (src/...:25-31). Check: compare with the lifecycle rules.
```

Leads may be written by `recon` or by any axis. **The axis that owns a lead
closes it** before it finishes, by rewriting the bullet's status:

- `promoted to F-SEC-006`
- `closed: <why it is not a weakness, with pointer>`
- `open: <what would settle it, and who: agent, auditor, or owner>`

No lead is left without a status. Reason: an unexplained lead reads either as
a hidden finding or as work not done. Leads in the file of an axis outside
the plan have no owner to close them: they carry `open: axis not requested`
until that axis runs.

## Questions for the auditor

Questions only the auditor or the owner can answer (an intended behaviour, a
production setting, a command the agent may not run). One per line, with the
lead or finding it affects. The kickoff's end report collects them.

### Recording an answer

Whichever session receives the answer records it in two places: under the
question (`**Answer (YYYY-MM-DD):** ...`) and in the finding concerned, as an
`**Auditor answer.**` paragraph after `**Verification.**`. These labels stay in
English like the others; the answer itself is in the engagement language. If the answer
changes the finding (rating, remediation, `promptable`, `resolution:
accepted`), apply the change in place with its reason, under the same rules as `verify-findings`:
every sentence stating the old value is updated. An answer cannot set
`status`; a claim it adds that the code does not show is a lead.

## Coverage section

Every axis file starts with what the axis could and could not see, area by
area, as a list or a table. Statuses:

- `evaluated`: looked at fully, with or without findings;
- `partial`: looked at, with a stated gap;
- `not-evaluable`: a required capability was missing (name it);
- `not-requested`: the auditor did not ask for this axis or area.

`not-evaluable` and `not-requested` are different facts and a report must not
merge them. An axis that cannot be evaluated writes `not-evaluable` with the
missing capability, and no findings. It does not guess.

State the sources of evidence: commit audited, where dependency code was read
from, which running target was observed and at which commit and environment.
If the running target does not serve the audited commit, dynamic evidence only
covers what the difference does not touch, and the coverage says so.
