---
name: audit-setup
description: Configure the auditor profile once per machine (agent, tools, severity scale, report language). Run before the first audit, or when other audit skills report a missing profile.
disable-model-invocation: true
---

# audit-setup

Version: 0.4.0 (audit skills, see CHANGELOG)

Create or update the **auditor profile**: everything that is stable across
engagements. Per-engagement facts (scope, access, client) do NOT belong here;
they belong to `audit-kickoff`.

Output: `~/.config/audit-skills/profile.md`

## Why two levels

The profile has the lifetime of the auditor. The engagement file has the
lifetime of one audit. Merging them forces the auditor to re-answer stable
questions on every engagement, so they stay separate.

## Process

1. **Detect before asking.** Probe the environment and record what is found:
   - Shell available? Which of these CLIs are on PATH: `semgrep`, `gitleaks`,
     `trivy`, `lighthouse`, `pa11y`, `axe`, language-native audit commands
     (`composer`, `npm`, `pip-audit`).
   - Any code-graph tool reachable (e.g. a GitNexus MCP server)?
   - Any browser automation tool reachable?
   - Can this agent spawn sub-agents?
2. **Confirm detections** with the auditor in one message. Do not ask about
   anything that was detected unambiguously.
3. **Ask only what cannot be detected**, up to three questions per message,
   numbered, each with a recommended answer, so the auditor can reply
   "1 ok, 2 b, 3 ok". Use the agent's structured question tool if it has
   one. The questions below are independent and fit in two batches:
   - Auditor background: technical peer (assumed default) or not.
   - Default report language.
   - Severity scale: keep the default in `finding-format`, or supply a custom
     one (must keep the same number of levels).
   - Reference frameworks to cite by default (e.g. OWASP ASVS, WCAG 2.2 or
     RGAA, CNIL guidance).
   - Where engagement workspaces live on disk.
4. **Write the profile** using the template below.

Every question must have a consumer: if no skill reads the answer, do not ask
it.

## Profile template

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

## Invariants (not configurable)

These are deliberately absent from the profile. Do not add switches for them.

- Findings require evidence. Reason: an audit finding has no test suite to
  catch it when it is wrong.
- The client repository is never written to. Reason: an audit must not alter
  what it measures, and must leave no trace in client history.
- Exploitation detail never enters a remediation prompt. Reason: prompts are
  designed to be pasted into third-party tools.
- Coverage limits are always reported. Reason: an unreported gap reads as a
  clean bill of health.
- Active testing requires a recorded authorization from the target's owner.
  Reason: without it the auditor carries the legal risk.
