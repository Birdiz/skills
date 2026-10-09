# skills

Agent skills for running technical audits: code quality, architecture,
security, privacy, accessibility, SEO and performance.

Small, composable, and readable by any coding agent. The structure is
inspired by [mattpocock/skills](https://github.com/mattpocock/skills); the
content is specific to auditing.

## Status

Early. The foundation, a first axis (`app-security`), verification and
reporting are written, and have run on a real codebase. Two more static axes
(`code-quality`, `architecture`) have run once, through verification.
The other axes, remediation grouping and tickets are not written. See [Roadmap](#roadmap).

## Install

**Claude Code (recommended): as a plugin.** Skills are namespaced
`birdiz-skills:<name>` and update with each release.

```
/plugin marketplace add Birdiz/skills
/plugin install birdiz-skills@birdiz
```

To update: `/plugin marketplace update birdiz`.

**Other agents, or to edit the skills:** copy the folders under
`skills/audit/` into the agent's skills directory.

Pick one: installing both, or keeping copies saved in your Claude account,
gives you every skill twice.

## Flow

1. `/audit-setup`, once per machine: the auditor profile.
2. `/audit-kickoff`, once per audit: scope, access, authorization, audience.
3. `recon`: one shared map of the codebase.
4. Axes write findings in a common format (`app-security`, `code-quality`,
   `architecture` so far).
5. `verify-findings`, in a separate context: confirmed, refuted, or left
   unverified with a reason.
6. `audit-report`: the deliverables the engagement's audience requires.

## Skills

**User-invoked** (they orchestrate)

- [audit-setup](skills/audit/audit-setup/SKILL.md): configure the auditor
  profile: agent, tools, severity scale, language.
- [audit-kickoff](skills/audit/audit-kickoff/SKILL.md): frame one engagement
  and create its workspace.

**Model-invoked** (they hold the discipline)

- [finding-format](skills/audit/finding-format/SKILL.md): the schema and
  rules every finding follows.
- [recon](skills/audit/recon/SKILL.md): map an unfamiliar codebase before
  auditing it.
- [app-security](skills/audit/app-security/SKILL.md): the application
  security axis.
- [code-quality](skills/audit/code-quality/SKILL.md): defects, error
  handling, hotspots, duplication and tests, judged by their cost.
- [architecture](skills/audit/architecture/SKILL.md): boundaries,
  dependency direction, data ownership and failure between components.
- [verify-findings](skills/audit/verify-findings/SKILL.md): try to refute
  every finding from a context that did not write it.
- [audit-report](skills/audit/audit-report/SKILL.md): peer report,
  plain-language summary and remediation prompts, from verified findings.

A user-invoked skill may rely on model-invoked ones, never on another
user-invoked one.

## Design

- **Files are the contract.** Skills communicate through files in the
  engagement workspace, not through agent features. Sub-agents and MCP servers
  are optional accelerators. See [ADR 0001](docs/adr/0001-files-as-contract.md).
- **Two setup levels.** Auditor profile and engagement have different
  lifetimes. See [ADR 0002](docs/adr/0002-two-level-setup.md).
- **Invariants are not settings.** Evidence, read-only access, no exploit
  detail in prompts, declared coverage, recorded authorization for active
  tests. See
  [ADR 0003](docs/adr/0003-invariants-are-not-configurable.md).
- **One set of findings, several reports.** Peer report, plain-language
  summary and remediation prompts are projections of the same findings.

Vocabulary is defined in [CONTEXT.md](CONTEXT.md).

## Never commit an engagement

This repository holds skills only. Engagement workspaces contain confidential
findings and live elsewhere (`workspace_root` in the auditor profile).

## Roadmap

- Axes: `infra-security`, `privacy`, `accessibility`, `seo`, `performance`
- Remediations: group findings by fix, then render each one as a ticket, a
  vendor brief or an executable prompt
- Tickets: at kickoff, detect whether the target has an issue tracker and ask
  whether the agent may create tasks there; local files otherwise. Sensitive
  findings never go to a tracker that is not access-restricted
- A script that validates finding files against the schema

## License

MIT
