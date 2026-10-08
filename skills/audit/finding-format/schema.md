# Finding schema

A level-3 heading, a YAML block, four prose sections:

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

**Evidence.** What was observed, reproducibly.

**Technical explanation.** For a peer: cause, consequence, conditions; for a
severity off the axis grid, from which level and why.

**Plain-language explanation.** For a non-technical reader: what could go
wrong and why it matters, in everyday words, without exploit detail.

**Remediation.** The fix, and how to check it worked.
````

## IDs

`F-<AXIS>-<NNN>` for findings, `L-<AXIS>-<NN>` for leads, never reused or
renumbered.
Axis codes: `QUA` code quality, `ARC` architecture, `SEC` app security, `INF`
infra security, `PRI` privacy, `A11Y` accessibility, `SEO`, `PERF`
performance.

## Lead

One bullet, with pointers and the check that settles it; its status is
rewritten at the end:

```markdown
- **L-SEC-04 Consent written outside the lifecycle.** Controller saves the
  flag directly (src/...:25-31). Check: compare with the lifecycle rules.
  open: intended behaviour; auditor.
```

## Default severity scale

| Level | Meaning |
|---|---|
| critical | Exploitable now, or legal exposure now; data loss, takeover, or outage |
| high | Serious consequence, needs a realistic precondition |
| medium | Real weakness, limited consequence or hard to reach |
| low | Hygiene; raises cost or risk over time |
| info | Observation, no action required |

A custom scale from the auditor profile replaces the meanings and keeps five
levels. An axis grid maps onto these levels.
