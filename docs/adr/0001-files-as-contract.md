# 0001: Files are the contract between skills

Status: accepted, 2026-10-07

## Context

The skills must run on several coding agents. Sub-agents, parallel execution
and MCP servers exist on some and not on others.

## Decision

Skills communicate only through files in the engagement workspace:
`00-engagement.md`, `01-codebase-map.md`, `findings/<axis>.md`, `reports/`.
Each axis is a self-contained step that reads those files and writes its own.

Sub-agents, graph tools and MCP servers are optional accelerators. A skill
checks the auditor profile for them and has a path without them.

## Consequences

- An audit can be run as one session per axis, or in parallel where the agent
  allows it, with the same result.
- Independent verification is obtained by a fresh session that receives only
  the findings, not by a specific agent feature.
- The file formats become a public interface: changing them is a breaking
  change and goes in the changelog.
