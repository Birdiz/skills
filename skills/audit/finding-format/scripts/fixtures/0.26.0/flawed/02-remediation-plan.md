# Remediation plan
commit: 0badc0de
skill: remediation-plan@0.26.0
findings: 6 confirmed open, from findings/*.md read on 2026-10-12
generated: 2026-10-12

## Order

| # | Fix | Title | Severity | Effort | Executor | Waits for | Quick win |
|---|---|---|---|---|---|---|---|
| 1 | R-002 | Rate-limit login | high | M | code | R-009; Q-SEC-77 | no |
| 2 | R-001 | Secure the session cookie | low | M | code | — | yes |
| 3 | R-008 | Retention duration | medium | M | owner | Q-PRI-01 | no |
| 4 | R-009 | Analytics consent | high | S | code | — | maybe |
| 5 | R-005 | Dropped fix | low | S | code | — | no |
| 6 | R-010 | No section | low | S | code | — | no |
| 7 | R-011 | Low then high | low | S | code | — | no |
| 8 | R-012 | High after low | high | S | code | — | yes |
| 9 | R-013 | Waits for later | medium | S | code | R-014 | no |
| 10 | R-014 | Waited for | medium | S | code | — | yes |

## Fixes

### R-001 Secure the session cookie

```yaml
id: R-001
findings: [F-SEC-001]
grouping: single
status: open
severity: low
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations:
  - config/packages/framework.yaml:5
sources: {F-SEC-001: 111111111111}
```

**Why together.** Alone.

**Change.** Cookie secure.

**Check.** F-SEC-001: the header carries Secure.

### R-002 Rate-limit login

```yaml
id: R-002
findings: [F-SEC-002, F-SEC-099]
grouping: single
status: open
severity: high
effort: M
executor: code
promptable: true
sensitive: false
waits_for: [R-009, Q-SEC-77]
locations:
  - findings/app-security.md (F-SEC-002)
  - /tmp/elsewhere/file.php:1
sources: F-SEC-002
```

**Grouping.** Two findings.

**Change.** Add a limiter.

**Check.** Ten failures lock.

### R-3 Bad identifier

```yaml
id: R-003
findings: [F-SEC-005]
grouping: single
status: dropped
severity: low
effort: S
executor: owner
promptable: maybe
sensitive: false
waits_for: none
locations: []
```

**Grouping.** Alone.

**Change.** Nothing.

**Check.** Nothing.

### R-004 Done too early

```yaml
id: R-004
findings: [F-SEC-009]
grouping: single
status: done
severity: medium
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations: []
```

**Grouping.** Alone.

**Change.** Migrate the session.

**Check.** The id changes at login.

### R-005 Dropped fix

```yaml
id: R-005
findings: []
grouping: single
status: dropped
severity: low
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations: []
```

**Grouping.** Alone.

**Change.** Nothing.

**Check.** Nothing.

### R-006 Empty open fix

```yaml
id: R-006
findings: []
grouping: one-change
status: open
severity: low
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations: []
```

**Grouping.** None.

**Change.** Nothing.

### R-007 No block

Just prose.

### R-008 Retention duration

```yaml
id: R-008
findings: [F-PRI-001, F-SEC-001, F-SEC-007]
grouping: same-files
status: open
severity: medium
effort: M
executor: owner
promptable: false
sensitive: false
waits_for: [Q-PRI-01]
locations:
  - ./tickets/R-008.md
  - L-PRI-03
```

**Grouping.** Same files.

**Change.** Decide a duration.

**Check.** The policy names it.

### R-009 Analytics consent

```yaml
id: R-009
findings: [F-PRI-002]
grouping: single
status: open
severity: high
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations:
  - templates/base.html.twig:12
id: R-009
```

**Grouping.** Alone.

**Change.** Load after consent.

**Check.** No request before the choice.

### R-011 Low then high

```yaml
id: R-011
findings: [F-SEC-005]
grouping: single
status: open
severity: low
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations:
  - src/Error.php:1
```

**Grouping.** Alone.

**Change.** Debug off.

**Check.** No trace.

### R-012 High after low

```yaml
id: R-012
findings: [F-SEC-006]
grouping: single
status: open
severity: high
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations:
  - src/Headers.php:1
```

**Grouping.** Alone.

**Change.** Add CSP.

**Check.** Header present.

### R-013 Waits for later

```yaml
id: R-013
findings: [F-SEC-004]
grouping: single
status: open
severity: medium
effort: S
executor: code
promptable: true
sensitive: false
waits_for: [R-014, R-004]
locations:
  - src/Upload.php:3
```

**Grouping.** Alone.

**Change.** Lower the limit.

**Check.** 6 MB refused.

### R-014 Waited for

```yaml
id: R-014
findings: [F-SEC-008]
grouping: single
status: open
severity: medium
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations:
  - src/Controller/Login.php:14
```

**Grouping.** Alone.

**Change.** Allow-list.

**Check.** External target refused.

### R-001 Twice

```yaml
id: R-001
findings: [F-SEC-001]
grouping: single
status: dropped
severity: medium
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations: []
```

**Grouping.** Alone.

**Change.** Duplicate.

**Check.** Duplicate.

The cookie fix: `config/packages/framework.yaml:5` "the name of a fix", and `src/Missing.php:1`.
