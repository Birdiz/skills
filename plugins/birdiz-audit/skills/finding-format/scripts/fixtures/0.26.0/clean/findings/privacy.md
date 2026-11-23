# privacy

## Coverage

skill: privacy@0.26.0 (2026-10-11), tools: []

| Area | Status | Notes |
|---|---|---|
| Retention | evaluated | F-PRI-001. |
| Minors | not-requested | Out of scope. |

## Findings

### F-PRI-001 No retention duration

```yaml
id: F-PRI-001
axis: privacy
status: confirmed
verification: {by: sub-agent, on: 2026-10-12, sha: f055024f7a40}
severity: low
confidence: high
evidence_regime: declarative
effort: M
resolution: open
sensitive: false
promptable: false
locations:
  - Q-PRI-01
references:
  - GDPR art. 5(1)(e)
commit: a1b2c3d
```

**Evidence.** Q-PRI-01: no duration decided. `law.txt:2` "Information to be provided"
and `tool-output/privacy/law.txt:1` « Article 13 ».

**Technical explanation.** Accounts are kept without a limit.

**Plain-language explanation.** Data is kept longer than needed.

**Remediation.** Decide a duration and delete after it.

**Verification.** by: sub-agent, 2026-10-12. Confirmed with the owner's answer.

## Leads

- **L-PRI-01 Retention.** moved from app-security; closed: settled by F-PRI-001.

## Questions for the auditor

- **Q-PRI-01** (Retention) How long are accounts kept?
  **Answer (2026-10-10, owner):** "No duration decided".
