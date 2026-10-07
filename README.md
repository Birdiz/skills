# skills

Agent skills for running technical audits: code quality, architecture,
security, privacy, accessibility, SEO and performance.

Small, composable, and readable by any coding agent. The structure is
inspired by [mattpocock/skills](https://github.com/mattpocock/skills); the
content is specific to auditing.

## Status

Early. The foundation and a first axis (`app-security`) are written; the
other axes, verification, reporting and tickets are not. Nothing has been run
on a real audit yet. See [Roadmap](#roadmap).

## Install

The layout follows the `skills/<category>/<name>/SKILL.md` convention, so the
`skills` installer should pick it up (not yet tested against this repo):

```
npx skills@latest add Birdiz/skills
```

Or copy the folders under `skills/audit/` into your agent's skills directory.

## Flow

1. `/audit-setup`, once per machine: the auditor profile.
2. `/audit-kickoff`, once per audit: scope, access, authorization, audience.
3. `recon`: one shared map of the codebase.
4. Axes write findings in a common format (`app-security` so far).
5. Verification, then reports (to come).

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

A user-invoked skill may rely on model-invoked ones, never on another
user-invoked one.

## Design

- **Files are the contract.** Skills communicate through files in the
  engagement workspace, not through agent features. Sub-agents and MCP servers
  are optional accelerators. See [ADR 0001](docs/adr/0001-files-as-contract.md).
- **Two setup levels.** Auditor profile and engagement have different
  lifetimes. See [ADR 0002](docs/adr/0002-two-level-setup.md).
- **Invariants are not settings.** Evidence, read-only access, no exploit
  detail in prompts, declared coverage. See
  [ADR 0003](docs/adr/0003-invariants-are-not-configurable.md).
- **One set of findings, several reports.** Peer report, plain-language
  summary and remediation prompts are projections of the same findings.

Vocabulary is defined in [CONTEXT.md](CONTEXT.md).

## Never commit an engagement

This repository holds skills only. Engagement workspaces contain confidential
findings and live elsewhere (`workspace_root` in the auditor profile).

## Roadmap

- Run `app-security` on a real codebase and fix the finding schema where it
  hurts, before writing the other axes
- Axes: `code-quality`, `architecture`, `infra-security`, `privacy`,
  `accessibility`, `seo`, `performance`
- `verify-findings`: refutation pass by a context that did not produce them
- Remediations: group findings by fix, then render each one as a ticket, a
  vendor brief or an executable prompt
- Tickets: at kickoff, detect whether the target has an issue tracker and ask
  whether the agent may create tasks there; local files otherwise. Sensitive
  findings never go to a tracker that is not access-restricted
- `audit-report`
- A script that validates finding files against the schema

## License

MIT
