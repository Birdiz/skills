# Remediation plan
commit: a1b2c3d4e5f6
skill: remediation-plan@0.26.0
tools: [python3@3.9.6]
findings: 2 confirmed open, from findings/*.md read on 2026-10-21
generated: 2026-10-21

## Order

| # | Fix | Title | Severity | Effort | Executor | Waits for | Quick win |
|---|---|---|---|---|---|---|---|
| 1 | R-001 | Secure the session cookie | medium | S | code | — | yes |
| 2 | R-003 | Decide a retention duration | low | M | owner | Q-PRI-01 | no |

## Fixes

### R-001 Secure the session cookie

```yaml
id: R-001
findings: [F-SEC-001]
grouping: single
status: open
severity: medium
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations:
  - config/packages/framework.yaml:5
sources: {F-SEC-001: f96df0228f03}
```

**Grouping.** Alone.

**Change.** Set the cookie to secure. `config/packages/framework.yaml:5` "cookie_secure".

**Check.** F-SEC-001: the header carries Secure.

### R-002 Migrate the session at login

```yaml
id: R-002
findings: []
grouping: single
status: done
severity: high
effort: S
executor: code
promptable: true
sensitive: true
waits_for: []
locations: []
```

**Grouping.** Alone.

**Change.** Migrate the session.

**Check.** F-SEC-002: the id changes at login.

### R-003 Decide a retention duration

```yaml
id: R-003
findings: [F-PRI-001]
grouping: single
status: open
severity: low
effort: M
executor: owner
promptable: false
sensitive: false
waits_for: [Q-PRI-01]
locations:
  - src/Account/Retention.php
sources: {F-PRI-001: f055024f7a40}
```

**Grouping.** Alone.

**Change.** Decide and implement a duration.

**Check.** F-PRI-001: accounts older than the duration are gone.

## Discrepancies

None.
