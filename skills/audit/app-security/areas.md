# app-security areas and severity

## Areas

- **Authentication**: credential storage, login and reset flows, token issuance and expiry, MFA.
- **Session**: cookie flags, fixation, invalidation on logout and password change.
- **Authorization**: per-route checks, object-level access (can A read B's record), role escalation, tenant isolation.
- **Injection**: SQL and NoSQL, command, template, LDAP, header, log.
- **Output handling**: XSS, content types, unsafe HTML rendering.
- **Server-side requests**: SSRF, open redirects, webhook targets.
- **Files**: upload type and size, path traversal, storage location, download authorization.
- **Deserialization**: untrusted object deserialization, unsafe parsers.
- **Secrets**: hard-coded credentials, keys in history, secrets in logs or client bundles.
- **Cryptography**: home-made schemes, weak algorithms, static IVs, predictable randomness.
- **Dependencies**: known-vulnerable versions actually present, abandoned packages.
- **Configuration**: debug modes, CORS, security headers, default accounts, exposed admin or metrics endpoints.
- **Errors and logs**: stack traces to clients, personal data or tokens in logs.
- **Abuse**: rate limiting on auth and costly endpoints, enumeration, business-logic bypass.

## Severity grid

Who can reach it, and what they get:

| | Unauthenticated | Any authenticated user | Privileged user only |
|---|---|---|---|
| Takeover, code execution, bulk data access | critical | critical | high |
| Another user's data, privilege escalation | critical | high | medium |
| Availability, abuse of the service (lockout, mail flooding) | medium | medium | low |
| Limited disclosure (account existence, metadata), integrity of own data | medium | low | low |
| Hardening gap, no direct consequence | low | low | info |

Moves of one level: `finding-format`, Rating.
