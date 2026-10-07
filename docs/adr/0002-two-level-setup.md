# 0002: Two setup levels, profile and engagement

Status: accepted, 2026-10-07

## Context

A single setup step would mix answers that never change (which agent, which
tools, which severity scale) with answers that change every audit (scope,
access, authorization, audience).

## Decision

Two skills, two files, two lifetimes:

- `audit-setup` writes the auditor profile, once per machine.
- `audit-kickoff` writes the engagement file, once per audit.

Both detect what they can before asking, and every question must name the
skill that reads its answer.

## Consequences

- Nothing personal to an auditor is hard-coded in a skill, so the set can be
  shared.
- Other skills refuse to run without the engagement file rather than assume
  defaults.
- A question with no consumer is removed, which keeps both interviews short.
