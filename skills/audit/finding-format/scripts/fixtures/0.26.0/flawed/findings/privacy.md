# privacy

## Coverage

Run on 2026-10-11 with semgrep.

| Area | Status | Notes |
|---|---|---|
| Inventory | evaluated | F-PRI-001. |
| Retention | partial | Q-PRI-01. |

## Leads

- **L-PRI-02 Moved away.** closed: moved to app-security as L-SEC-04.
- **L-PRI-03 Retention of logs.** open: owner, Q-PRI-01.

## Findings

### F-PRI-001 Accounts kept ten years

```yaml
id: F-PRI-001
axis: privacy
status: confirmed
verification: {by: sub-agent, on: 2026-10-12}
severity: medium
confidence: high
evidence_regime: declarative
effort: M
resolution: open
sensitive: false
promptable: false
locations:
  - Q-PRI-01
  - client-docs/policy.md:3
commit: a1b2c3d
references:
  - GDPR art. 5(1)(e)
```

**Evidence.** `policy.md:3` "We keep accounts for ten years." and
`law.txt:2` "Information to be provided". `client-docs/policy.md:9` "nothing".
`helper.php:4` "a helper". Also `tool-output/privacy/law.txt:1` « Article 13 »
and `law.txt:1` “Article 12”.

**Technical explanation.** No retention limit.

**Plain-language explanation.** Data is kept too long.

**Remediation.** Set a duration.

**Verification.** by: sub-agent, 2026-10-12. Confirmed with the owner.

### F-PRI-002 Analytics without consent

```yaml
id: F-PRI-002
axis: privacy
status: confirmed
verification: {by: sub-agent, on: 2026-10-12}
severity: high
confidence: high
evidence_regime: declarative
effort: S
resolution: fixed
sensitive: false
promptable: true
locations:
  - https://acme.example/
commit: a1b2c3d
references: []
```

**Evidence.** A tracker loads before any choice. Not tied to a question.

**Technical explanation.** Consent comes after.

**Plain-language explanation.** Visitors are tracked first.

**Remediation.** Wait for consent.

**Verification.** by: sub-agent, 2026-10-12. Seen.
Fix checked 2026-10-12 at 9f8e7d6: not fixed, the tracker still loads.

## Questions for the auditor

- **Q-PRI-01** (Retention) How long? **Asked (2026-10-11), not answered.**
- **Q-PRI-02** (Transfers) Where are backups? **Answer (2026-10-14, owner):** "eu-west".
