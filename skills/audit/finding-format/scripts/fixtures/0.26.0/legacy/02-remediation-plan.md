# Remediation plan
commit: a1b2c3d
skill: remediation-plan@0.20.0
tools: []
findings: 2 confirmed open
generated: soon

## Order

| # | Fix | Title | Severity | Effort | Executor | Waits for | Quick win |
|---|---|---|---|---|---|---|---|
| 1 | R-001 | Titles | low | S | code | R-005 | no |

## Fixes

### R-001 Titles

```yaml
id: R-001
findings: [F-SEO-001]
grouping: single
status: open
severity: low
effort: S
executor: robot
promptable: true
waits_for: [R-005]
locations:
  - templates/base.html.twig:3
sources: {F-SEO-001: 333333333333}
```

**Grouping.** Alone.

**Change.** Titles.

**Check.** F-SEO-001: distinct titles.

## Discrepancies

None.
