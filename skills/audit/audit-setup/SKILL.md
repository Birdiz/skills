---
name: audit-setup
description: Configure the auditor profile once per machine (agent, tools, severity scale, report language). Run before the first audit, or when other audit skills report a missing profile.
disable-model-invocation: true
---

# audit-setup

Version: 0.10.0 (audit skills, see CHANGELOG)

Write the **auditor profile**: what stays true across engagements. Scope,
access and client belong to `audit-kickoff`.

Output: `~/.config/audit-skills/profile.md`

## Process

1. **Detect**: shell; `docker` (any tool an axis names can then run from a
   pinned image); which of `semgrep`, `gitleaks`, `trivy`, `lizard`, `scc`,
   `jscpd`, `lighthouse`, `pa11y`, `axe` and language-native audit commands
   (`composer`, `npm`, `pip-audit`...) are on PATH; a reachable
   code-graph tool (e.g. a GitNexus MCP server); a browser automation tool;
   sub-agents.
2. **Confirm** the detections in one message, asking only about ambiguous
   ones.
3. **Interview in rounds**: each round asks the frontier (questions whose
   prerequisites are settled), at most three, numbered, each with a
   recommended answer ("1 ok, 2 b, 3 ok"), through the agent's structured
   question tool when it has one. Two rounds cover:
   - auditor background: technical peer (default) or not;
   - default report language;
   - severity scale: the `finding-format` default, or a custom one with the
     same number of levels;
   - frameworks cited by default (OWASP ASVS, WCAG 2.2 or RGAA, CNIL
     guidance...);
   - where engagement workspaces live.
4. **Write the profile**:

```markdown
# Auditor profile
version: 1
updated: <YYYY-MM-DD>

## Environment
agent: <name>
sub_agents: <yes|no>
shell: <yes|no>
cli_tools: [<detected list>]
graph_tool: <none|name>
browser_tool: <none|name>

## Defaults
report_language: <fr|en|...>
severity_scale: <default|custom, see below>
frameworks: [<list>]
workspace_root: <path>
```

The profile holds only questions with two legitimate answers and a skill that
reads the answer. The invariants
have no switch: evidence for every finding, a read-only audited repository, no
exploitation detail in remediation prompts, coverage limits always reported,
active testing only with the owner's recorded authorization.
