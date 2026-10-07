# 0003: Invariants are not configurable

Status: accepted, 2026-10-07

## Context

Setup absorbs what varies between audits. It is tempting to make everything a
setting, including the rules that protect the quality of the audit.

## Decision

A question belongs in setup only if two legitimate answers exist. The
following have one, and are written into the skills with their reason:

1. **A finding requires reproducible evidence.** Nothing downstream catches a
   wrong finding the way a test catches wrong code.
2. **The audited repository is never written to.** An audit must not alter
   what it measures or leave a trace in client history.
3. **No exploitation detail in remediation prompts.** Prompts are made to be
   pasted into third-party tools and leave the confidential perimeter.
4. **Coverage limits are always reported.** An unreported gap reads as a
   clean result.
5. **Active testing requires written authorization.** Without it the auditor
   carries the legal risk.

## Consequences

- No profile or engagement field disables these.
- Anyone forking the set can change them, and can see what they give up.
