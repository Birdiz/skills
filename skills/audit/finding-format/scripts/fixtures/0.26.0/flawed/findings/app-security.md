# app-security

## Coverage

skill: app-security@0.26.0 (2026-10-11), tools: [semgrep@1.0]

Lead pass 2026-10-13 by app-security@0.26.0: L-SEC-04 taken up.

| Area | Status | Notes |
|---|---|---|
| Authentication | evaluated | F-SEC-001. |
| Session | evaluated (light) | F-SEC-002. |
| Files | partial | Waits for Q-SEC-01. |
| Secrets | done | Nothing. |
| Cloud | not-evaluable | No access. |
| Payments | not-requested | Out of scope. |
| Headers | | Empty status. |

| Tool | Version |
|---|---|
| semgrep | 1.0 |

## Findings

### F-SEC-001 Session cookie set without Secure flag

```yaml
id: F-SEC-001
axis: app-security
status: confirmed
verification: {by: sub-agent, on: 2026-10-10, sha: 000000000000}
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
At the later commit, `9f8e7d6:src/Controller/Login.php:3` "session->migrate(true)".

**Technical explanation.** The cookie travels over plain HTTP.

**Plain-language explanation.** Someone on the same network can read it.

**Remediation.** Set `cookie_secure: auto`; check the header.

**Verification.** by: sub-agent, 2026-10-10. Reproduced.

**Auditor answer.** Q-SEC-01, answer 2026-10-12: severity kept.

### F-SEC-002 Login has no rate limit

```yaml
id: F-SEC-002
axis: app-security
status: unverified
severity: high
confidence: medium
evidence_regime: declarative
effort: M
resolution: open
sensitive: yes
promptable: false
locations:
  - src/Controller/Login.php:10
commit: a1b2c3d4e5f6
references: ["CWE-307", 'OWASP [A07]', {a: b}]
impact: brute force   # legacy key
owner_note: "ask, again # not a comment"
```

**Evidence.** `src/Controller/Login.php:10` "password_verify($request->get('password'), $user->hash)"
and `src/Controller/Login.php:4` "final class Login". The owner says nothing limits attempts.

**Technical explanation.** Unlimited attempts.

**Plain-language explanation.** Passwords can be guessed.

**Remediation.** Add a limiter.

### F-QUA-003 Debug route left open

```yaml
id: F-QUA-003
axis: app-security
status: unverified
severity: severe
confidence: sure
evidence_regime: static
resolution: open
sensitive: false
promptable: true
locations: []
commit: zzz123
references: none
```

**Evidence.** `src/Debug.php:3` "debug".

**Remediation.** Remove it.

**Technical explanation.** Exposes internals.

**Technical explanation.** Said twice.

### F-SEC-004 Upload size unbounded

```yaml
id: F-SEC-004
axis: privacy
status: confirmed
verification: {by: robot, on: yesterday, sha: abc}
severity: low
confidence: high
evidence_regime: static
effort: S
resolution: fixed
sensitive: false
promptable: true
locations:
  - src/Upload.php:3
commit: 0badc0de
references: []
```

**Evidence.** `src/Upload.php:3` "MAX_UPLOAD = 50 * 1024 * 1024".

**Technical explanation.** Large files fill the disk.

**Plain-language explanation.** The server can run out of space.

**Remediation.** Lower the limit.

**Verification.** by: robot. Seen.

### F-SEC-005 Verbose error page

```yaml
id: F-SEC-050
axis: app-security
status: confirmed
verification: {by: new session, on: 2026-10-10}
severity: low
confidence: high
evidence_regime: dynamic
effort: S
resolution: accepted
sensitive: false
promptable: true
locations:
  - https://acme.example/error
commit: a1b2c3d
references: []
```

**Evidence.** The error page shows a stack trace; `src/Controller/Login.php:12` "session->set('user'".

**Technical explanation.** Paths leak.

**Plain-language explanation.** Internal details show.

**Remediation.** Turn debug off.

**Verification.** by: new session, 2026-10-10. Seen.

**Auditor answer.** Kept by decision, the owner prefers it.

### F-SEC-006 Missing CSP

```yaml
id: F-SEC-006
axis: app-security
status: confirmed
severity: info
confidence: low
evidence_regime: dynamic
effort: L
resolution: accepted
sensitive: false
promptable: true
locations:
  - https://acme.example/
commit: a1b2c3d
references: []
```

**Evidence.** No `Content-Security-Policy` header.

**Technical explanation.** No defence in depth.

**Plain-language explanation.** One layer less.

**Remediation.** Add a policy.

### F-SEC-007 Password reset token reusable

```yaml
id: F-SEC-007
axis: app-security
status: confirmed
verification: {by: sub-agent, on: 2026-10-10}
severity: high
confidence: high
evidence_regime: static
effort: M
resolution: fixed
sensitive: true
promptable: true
locations:
  - src/Controller/Login.php:13
commit: a1b2c3d
references: []
```

**Evidence.** `src/Controller/Login.php:13` "$this->session->set('user', $user->id);".
`src/Controller/Login.php:9-11` "find($request->get('email')) […] Invalid credentials",
`src/Controller/Login.php:10` "password_verify(<redacted>)" and `vendor/acme/lib/src/Client.php:2` "verify = false".

**Technical explanation.** Tokens are not invalidated.

**Plain-language explanation.** An old link still works.

**Remediation.** Invalidate on use.

**Verification.** by: sub-agent, 2026-10-10. Reproduced.
Fix checked 2026-10-20 at 9f8e7d6: fixed by 1234abc (PR #7).

### F-SEC-008 Open redirect

```yaml
id: F-SEC-008
axis: app-security
status: refuted
severity: medium
confidence: medium
evidence_regime: static
effort: S
resolution: open
sensitive: false
promptable: true
locations:
  - src/Controller/Login.php:14
commit: a1b2c3d
references: []
verification: {by: sub-agent}
```

**Evidence.** `src/Controller/Login.php:14` "redirect($request->get('next'))".

**Technical explanation.** Unchecked target.

**Plain-language explanation.** Links can send users elsewhere.

**Remediation.** Allow-list targets.

### F-SEC-009 Session fixation

```yaml
id: F-SEC-009
axis: app-security
status: unverified
severity: medium
confidence: medium
evidence_regime: static
effort: S
resolution: open
sensitive: false
promptable: true
locations:
  - src/Controller/Login.php:13
commit: a1b2c3d
references: []
```

**Evidence.** `src/Controller/Login.php:13` "session->set('user'". Fixed later: Fix checked 2026-10-21 at 9f8e7d6: in part: migrate added.

**Technical explanation.** The session id survives login.

**Plain-language explanation.** An attacker can plant a session.

**Remediation.** Migrate the session.

**Auditor answer.** 2026-10-10: before the note.

**Verification.** by: sub-agent, 2026-10-11. Note without a key.

### F-SEC-001 Duplicate heading

```yaml
id: F-SEC-001
axis: app-security
status: unverified
severity: low
confidence: low
evidence_regime: static
effort: S
resolution: open
sensitive: false
promptable: false
locations:
  - src/Upload.php:2
commit: a1b2c3d
references: []
key: one
key: two
flags: {a: 1, b}
	this line is unreadable
```

**Evidence.** `src/Upload.php:2` "Upload limit".

**Technical explanation.** Duplicate.

**Plain-language explanation.** Duplicate.

**Remediation.** None.

### F-SEC-010 No YAML here

Just prose, no block.

### Notes about sessions

Free text under a heading that is not a finding.

## Leads

- **L-SEC-01 Cookie flags.** framework.yaml:5. Check: read it.
  promoted to F-SEC-001.
- **L-SEC-02 Upload size.** src/Upload.php:3. Check: read it. open: owner,
  Q-SEC-01.
- **L-SEC-03 Admin panel.** No status at all.
- **L-SEC-1 Short ID.** closed: nothing there.
- **L-SEC-02 Twice.** closed: duplicate.
- **L-SEC-04 Moved here.** open: moved from privacy (L-PRI-02), waits.
- **L-SEC-05 From verification.** open: from verify-findings 2026-10-20; the agent saw more.
- **L-SEC-06 Payments flow.** open: axis not requested.
- **L-SEC-07 Promoted elsewhere.** promoted to F-SEC-099.
- **L-SEC-08 Remains.** closed: remains of F-SEC-077's fix.
- A bullet without an ID.
Loose paragraph line.
- **L-SEC-09 Settled.** closed: settled by F-SEC-001.

## Leads for other axes

- **privacy: Cookie scope.** framework.yaml:6.
- **payments: Card storage.** src/Pay.php:1.
- Cookie lifetime, no axis given.
- **privacy: Retention.** moved to L-PRI-03.
- **privacy: Logs.** moved to L-PRI-09.

## Questions for the auditor

- **Q-SEC-01** (Files) Which upload size? Proposal: 5 MB (src/Upload.php:3).
  **Answer (2026-10-12, owner):** "5 MB" accepts the proposal: 5 MB.
- **Q-SEC-02** (Session) Which lifetime? Proposal: 1 hour.
  **Answer (2026-10-12, owner):** "1 hour".
  **Applied (2026-10-13).**
- **Q-SEC-3** Which host? **Asked (2026-10-12), not answered.**
- Which CDN? **Asked 2026-10-12, not answered**
- **Q-SEC-04** Which region? **Answer 2026-10-12:** "eu".
- **Q-SEC-05** Which logs? **Answer (2026-10-11, owner):** "none". **Applied 2026-10-13.**
- **Q-SEC-01** Asked twice. **Asked (2026-10-12), not answered.**
- **Q-SEC-06** Same day. **Answer (2026-10-13, owner):** "yes".

## Notes

Mentions F-PRI-042 and Q-INF-07, which exist nowhere, and L-PRI-03, which does.

## Created on target

- Test account `audit-1@example.com`, kept.
