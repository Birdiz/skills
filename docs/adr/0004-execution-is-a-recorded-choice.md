# 0004: Running the project is a recorded choice of its owner

Status: accepted, 2026-11-01

## Context

The rules of engagement said the project never runs and the agent starts no
target. That protects the auditor: a third party's install scripts and tests
are code from outside, run with the auditor's permissions. It also has a cost.
On the first audit where the auditor owned a small application, the most
serious code-quality defects were found by running its tests in a throwaway
copy, which the rule forbids, on a coordinator's instruction no skill provided
for. The verifier then could not rerun them, and nothing said who starts a
target under active testing on localhost.

## Decision

The engagement records `execution: none | disposable-copy | local-target`.

- `none` is the default, and the only value on a third party's target. It is
  not an invariant of ADR 0003, because on one's own code two legitimate
  answers exist; on someone else's, one does.
- More than `none` needs the owner's own words, recorded like the testing
  authorization.
- What runs does so in a copy made for it, never in the working copy, with no
  `.env` or credential and a minimal environment, after the command has been
  read. A command that would reach a real service stays a lead.

## Consequences

- Evidence from running the project can be reproduced by the verifier.
- Tests can still have side effects a reading misses; the minimal environment
  limits them and does not remove them, so the value stays off by default.
- The validator refuses any other value on a third party's target.
