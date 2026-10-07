---
name: finding-format
description: The schema and rules every audit finding must follow (evidence, severity, confidence, effort, sensitivity). Use whenever writing, reviewing, or reading findings in an audit workspace, and before producing any audit report.
---

# finding-format

One schema for every finding, whatever the axis. Reports are projections of
the same findings, so a finding is written once and never re-authored per
deliverable.

## Where findings live

`<workspace>/findings/<axis>.md`, one file per axis. Each file has three
sections, in this order:

1. `## Coverage` (what was and was not evaluated)
2. `## Findings`
3. `## Leads` (suspicions without evidence)

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
impact: medium            # high | medium | low
sensitive: false
promptable: true
locations:
  - config/packages/framework.yaml:14
commit: a1b2c3d
references:
  - OWASP ASVS 3.4.1
```

**Evidence.** What was observed, with enough detail to reproduce: file and
line, the command run and its output, or the URL and the response.

**Technical explanation.** For a peer: cause, consequence, conditions.

**Plain-language explanation.** For a non-technical reader: what could go
wrong and why it matters to the business. No jargon, no exploit detail.

**Remediation.** The fix, and how to check it worked.
````

### IDs

`F-<AXIS>-<NNN>`, never reused, never renumbered. Axis codes: `QUA` code
quality, `ARC` architecture, `SEC` app security, `INF` infra security, `PRI`
privacy, `A11Y` accessibility, `SEO`, `PERF` performance.

## Rules

**No evidence, no finding.** Something suspected but not shown goes under
`## Leads`. Leads never reach a report as findings. Reason: nothing downstream
catches a wrong finding, and a plausible false positive costs the client real
work and the auditor credibility.

**Evidence must be reproducible by someone else.** A reader with the same
access must be able to see the same thing. "The code seems to" is a lead.

**Absence in a graph or a search is not proof.** Dependency injection, event
subscribers, config-driven routing and templates hide edges. Claims of dead
code or missing checks need the code read, not only a query.

**Never quote a secret.** Record where it is and what kind it is. Redact the
value, in every file, including evidence.

**Confidence is about the finding, severity about the consequence.** A
critical finding with low confidence stays critical and says so.

**Status starts at `unverified`.** Only a verification pass by a context that
did not produce the finding may set `confirmed` or `refuted`. Refuted findings
stay in the file, marked, so the same false positive is not rediscovered.

### `sensitive`

`true` when the finding, if leaked, helps an attacker or exposes personal
data: exploitable vulnerabilities, secret locations, misconfigurations
reachable from outside. Sensitive findings appear only in the confidential
report.

### `promptable`

`true` only when a coding agent could apply the remediation in the codebase.
`false` for human actions: rotating a key, signing a processor agreement,
enabling MFA, changing a DNS record.

### Quick win

Derived, never stored: `status: confirmed`, `impact` high or medium, and
`effort: S`.

## Default severity scale

| Level | Meaning |
|---|---|
| critical | Exploitable now, or legal exposure now; data loss, takeover, or outage |
| high | Serious consequence, needs a realistic precondition |
| medium | Real weakness, limited consequence or hard to reach |
| low | Hygiene; raises cost or risk over time |
| info | Observation, no action required |

A custom scale from the auditor profile replaces the meanings, not the number
of levels.

## Coverage section

Every axis file starts with what the axis could not see. One line per area:

```markdown
## Coverage
- evaluated: HTTP controllers, auth, session config
- partial: background workers (no runtime access, static only)
- not-evaluable: production headers (no URL provided)
```

An axis that cannot be evaluated with the capabilities in the engagement file
writes `not-evaluable` with the missing capability, and no findings. It does
not guess.
