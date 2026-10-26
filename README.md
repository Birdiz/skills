<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
  <img alt="birdiz/skills: agent skills for technical audits" src="docs/assets/banner-light.svg" width="100%">
</picture>
</p>

<p align="center">
  <a href=".claude-plugin/plugin.json"><img alt="version" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FBirdiz%2Fskills%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=E8772E"></a>
  <a href="#install"><img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-1B1F3B"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-5D6480"></a>
</p>

Agent skills for running technical audits: code quality, architecture,
security, privacy, accessibility, SEO and performance.

Small, composable, and readable by any coding agent. The structure is
inspired by [mattpocock/skills](https://github.com/mattpocock/skills); the
content is specific to auditing.

## Status

Early. The foundation, six axes (`app-security`, `code-quality`,
`architecture`, `accessibility`, `seo`, `performance`), verification and
reporting have run on a real codebase, together, through a full audit on a
local development stack. Two axes that rest partly on the owner's answers
(`infra-security`, `privacy`) have run once, with the answers step and lead
passes. Remediation grouping has run once, with the report on its plan.
Tickets, one per fix, have run to local files, then to a GitHub tracker
(four issues, one dependency link). A validator checks the form of findings
files and plans; it has run inside verification, the plan, the report and
tickets. See [Roadmap](#roadmap).

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

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/workflow-dark.svg">
  <img alt="Workflow: frame with audit-setup, audit-kickoff and recon; audit with eight axes, verify-findings and a lead pass on the owner's answers; deliver with remediation-plan, audit-report and tickets" src="docs/assets/workflow-light.svg">
</picture>

1. `/audit-setup`, once per machine: the auditor profile.
2. `/audit-kickoff`, once per audit: scope, access, authorization, audience.
3. `recon`: one shared map of the codebase.
4. Axes write findings in a common format (`app-security`,
   `infra-security`, `privacy`, `code-quality`, `architecture`,
   `accessibility`, `seo`, `performance`), and the questions only the owner
   can answer.
5. `verify-findings`, in a separate context: confirmed, refuted, or left
   unverified with a reason.
6. The owner's answers, then a lead pass of the axes they concern, verified
   in turn.
7. `remediation-plan`: the findings grouped into fixes, ordered.
8. `audit-report`: the deliverables the engagement's audience requires.
9. `tickets`: one per fix, in the target's tracker when the owner allows
   it, local files otherwise.

## Skills

**User-invoked** (they orchestrate)

- [audit-setup](skills/audit/audit-setup/SKILL.md): configure the auditor
  profile: agent, tools, severity scale, language.
- [audit-kickoff](skills/audit/audit-kickoff/SKILL.md): frame one engagement
  and create its workspace.

**Model-invoked** (they hold the discipline)

- [finding-format](skills/audit/finding-format/SKILL.md): the schema and
  rules every finding follows, and a validator for the form of findings
  files and plans (Python 3, standard library only).
- [recon](skills/audit/recon/SKILL.md): map an unfamiliar codebase before
  auditing it.
- [app-security](skills/audit/app-security/SKILL.md): the application
  security axis.
- [infra-security](skills/audit/infra-security/SKILL.md): images,
  containers, network exposure, edge, secrets delivery, pipeline, cloud,
  backups, from the IaC, the running target and the owner's answers.
- [privacy](skills/audit/privacy/SKILL.md): personal data inventory,
  information, consent, trackers, third parties, retention and rights,
  against the law that applies to the owner.
- [code-quality](skills/audit/code-quality/SKILL.md): defects, error
  handling, hotspots, duplication and tests, judged by their cost.
- [architecture](skills/audit/architecture/SKILL.md): boundaries,
  dependency direction, data ownership and failure between components.
- [accessibility](skills/audit/accessibility/SKILL.md): keyboard, names and
  roles, forms, contrast, reflow, against WCAG or RGAA, traced to templates.
- [seo](skills/audit/seo/SKILL.md): indexability, crawl, duplicates, titles,
  structured data, rated for the documented production configuration.
- [performance](skills/audit/performance/SKILL.md): server work per request,
  queries, remote calls, front-end loading, cost growing with data.
- [verify-findings](skills/audit/verify-findings/SKILL.md): try to refute
  every finding from a context that did not write it.
- [remediation-plan](skills/audit/remediation-plan/SKILL.md): group
  confirmed findings into fixes (one change, or the same files and
  executor), ordered, with who does each and what it waits for.
- [audit-report](skills/audit/audit-report/SKILL.md): peer report,
  plain-language summary and remediation prompts, from verified findings.
- [tickets](skills/audit/tickets/SKILL.md): one ticket per fix, following
  the target's conventions, in its tracker with the owner's permission
  (sensitive fixes only in an access-restricted one), local files
  otherwise; never edits a ticket once created.

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

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/projections-dark.svg">
  <img alt="One set of verified findings projected into a peer report, a summary and remediation prompts" src="docs/assets/projections-light.svg">
</picture>

Vocabulary is defined in [CONTEXT.md](CONTEXT.md); the visual identity in
[docs/brand.md](docs/brand.md).

## Never commit an engagement

This repository holds skills only. Engagement workspaces contain confidential
findings and live elsewhere (`workspace_root` in the auditor profile).

## Roadmap

- Run `infra-security` and `privacy` against a cloud account (cloud read)
- Clear the gn-platform report's DRAFT (`verify-findings` in revision mode,
  seo and accessibility lead passes, `remediation-plan`), then `audit-report`
  and `tickets` on 0.22.0 (uncovered changes, same-day runs, question kept)

## License

MIT
