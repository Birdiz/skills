# app-security

## Coverage

skill: app-security@0.26.0 (2026-10-11), tools: [semgrep@1.0]

| Area | Status | Notes |
|---|---|---|
| Session | evaluated | F-SEC-001. |
| Authentication | evaluated (light) | F-SEC-002. |
| Files | partial | Waits for Q-SEC-01. |
| Cloud | not-evaluable | No access. |

## Findings

### F-SEC-001 Session cookie set without Secure flag

```yaml
id: F-SEC-001
axis: app-security
status: confirmed
verification: {by: sub-agent, on: 2026-10-12, sha: f96df0228f03}
severity: medium          # critical | high | medium | low | info
confidence: high
evidence_regime: static
effort: S
resolution: open
sensitive: false
promptable: true
locations:
  - config/packages/framework.yaml:5
commit: a1b2c3d
references:
  - OWASP ASVS 5.0 3.3.1
```

**Evidence.** `config/packages/framework.yaml:5` "cookie_secure: false". Settles L-SEC-01.

**Technical explanation.** The cookie travels over plain HTTP.

**Plain-language explanation.** Someone on the same network can read it.

**Remediation.** Set `cookie_secure: auto`; check the header.

**Verification.** by: sub-agent, 2026-10-12. Reproduced.
Re-checked 2026-10-12, answer of 2026-10-11: no change.

**Auditor answer.** Q-SEC-01, answer 2026-10-11: severity kept.

### F-SEC-002 Session id kept at login

```yaml
id: F-SEC-002
axis: app-security
status: confirmed
verification: {by: new session, on: 2026-10-20, sha: edf27f760c58}
severity: high
confidence: high
evidence_regime: static
effort: S
resolution: fixed
sensitive: true
promptable: true
locations:
  - src/Controller/Login.php:13
commit: a1b2c3d4e5f6
references: []
```

**Evidence.** `src/Controller/Login.php:13` "$this->session->set('user', $user->id);"
and, later, `9f8e7d6:src/Controller/Login.php:3` "session->migrate(true)".

**Technical explanation.** The session id survives login.

**Plain-language explanation.** A planted session stays valid.

**Remediation.** Migrate the session at login.

**Verification.** by: new session, 2026-10-12. Reproduced.
Fix checked 2026-10-20 at 9f8e7d6: fixed by 1234abc (PR #7).

### F-SEC-003 Login has no rate limit

```yaml
id: F-SEC-003
axis: app-security
status: refuted
verification: {by: sub-agent, on: 2026-10-12, sha: be12bd5fcc88}
severity: medium
confidence: medium
evidence_regime: static
effort: M
resolution: open
sensitive: false
promptable: true
locations:
  - src/Controller/Login.php:9-11
commit: a1b2c3d
references: []
```

**Evidence.** `src/Controller/Login.php:9-11` "find($request->get('email')) […] Invalid credentials".

**Technical explanation.** Unlimited attempts.

**Plain-language explanation.** Passwords can be guessed.

**Remediation.** Add a limiter.

**Verification.** by: sub-agent, 2026-10-12. Refuted: the proxy limits attempts.

## Leads

- **L-SEC-01 Cookie flags.** framework.yaml:5. Check: read it.
  promoted to F-SEC-001.
- **L-SEC-02 Upload size.** src/Upload.php:3. Check: read it. open: owner,
  Q-SEC-01.
- **L-SEC-03 Payments.** open: axis not requested.

## Leads for other axes

- **privacy: Retention.** moved to L-PRI-01.

## Questions for the auditor

- **Q-SEC-01** (Files) Which upload size? Proposal: 5 MB (src/Upload.php:3).
  **Answer (2026-10-11, owner):** "5 MB" accepts the proposal: 5 MB.
  **Applied (2026-10-11).**
- **Q-SEC-02** (Session) Which lifetime? **Asked (2026-10-11), not answered.**

## Created on target

- Test account `audit-1@example.com`, kept.
