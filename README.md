<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-dark.svg">
  <img alt="birdiz/skills: agent skills for technical audits" src="docs/assets/banner-light.svg" width="100%">
</picture>
</p>

<p align="center">
  <a href="plugins/birdiz-audit/.claude-plugin/plugin.json"><img alt="version" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FBirdiz%2Fskills%2Fmain%2Fplugins%2Fbirdiz-audit%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=E8772E"></a>
  <a href="#install"><img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-1B1F3B"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-5D6480"></a>
</p>

Agent skills for running technical audits: code quality, architecture,
security, privacy, accessibility, SEO and performance.

Small, composable, and readable by any coding agent. The structure is
inspired by [mattpocock/skills](https://github.com/mattpocock/skills); the
content is specific to auditing.

A second plugin, `birdiz-review`, reviews pull requests written by coding
agents: where to read and why, what the review did not cover, and a
proposed verdict. It is new: its first version is the bare run, with no
detector that reads file contents yet.

## Status

Early. The foundation, six axes (`app-security`, `code-quality`,
`architecture`, `accessibility`, `seo`, `performance`), verification and
reporting have run on a real codebase, together, through a full audit on a
local development stack. Two axes that rest partly on the owner's answers
(`infra-security`, `privacy`) have run once, with the answers step and lead
passes. Remediation grouping has run once, with the report on its plan.
Tickets, one per fix, have run to local files, then to a GitHub tracker
(43 issues). Fixes the team made after the audit have
been checked at the later commit, through to the plan, the report and the
tickets. A validator checks the form of findings files and plans; it has
run inside verification, the plan, the report and tickets. A full audit has
also run on a second codebase, end to end, in one day. See
[Roadmap](#roadmap).

## Install

**Claude Code (recommended): as a plugin.** Skills are namespaced
`birdiz-audit:<name>` and update with each release.

```
/plugin marketplace add Birdiz/skills
/plugin install birdiz-audit@birdiz
```

To update: `/plugin marketplace update birdiz`.

The review skills are a separate plugin, installable with or without the
audit skills, namespaced `birdiz-review:<name>`:

```
/plugin install birdiz-review@birdiz
```

**Coming from `birdiz-skills` (0.26.0 or earlier):** the plugin is now
`birdiz-audit`, and its commands are `/birdiz-audit:<name>`. Workspaces
need no change.

```
/plugin uninstall birdiz-skills@birdiz
/plugin marketplace update birdiz
/plugin install birdiz-audit@birdiz
```

**Other agents, or to edit the skills:** copy the folders under
`plugins/birdiz-audit/skills/`, and `plugins/birdiz-audit/core/`, into the
agent's skills directory: the validator looks for `core/` above its own
folder.

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

- [audit-setup](plugins/birdiz-audit/skills/audit-setup/SKILL.md): configure the auditor
  profile: agent, tools, severity scale, language.
- [audit-kickoff](plugins/birdiz-audit/skills/audit-kickoff/SKILL.md): frame one engagement
  and create its workspace.

**Model-invoked** (they hold the discipline)

- [finding-format](plugins/birdiz-audit/skills/finding-format/SKILL.md): the schema and
  rules every finding follows, and a validator for the form of findings
  files and plans (Python 3, standard library only).
- [recon](plugins/birdiz-audit/skills/recon/SKILL.md): map an unfamiliar codebase before
  auditing it.
- [app-security](plugins/birdiz-audit/skills/app-security/SKILL.md): the application
  security axis.
- [infra-security](plugins/birdiz-audit/skills/infra-security/SKILL.md): images,
  containers, network exposure, edge, secrets delivery, pipeline, cloud,
  backups, from the IaC, the running target and the owner's answers.
- [privacy](plugins/birdiz-audit/skills/privacy/SKILL.md): personal data inventory,
  information, consent, trackers, third parties, retention and rights,
  against the law that applies to the owner.
- [code-quality](plugins/birdiz-audit/skills/code-quality/SKILL.md): defects, error
  handling, hotspots, duplication and tests, judged by their cost.
- [architecture](plugins/birdiz-audit/skills/architecture/SKILL.md): boundaries,
  dependency direction, data ownership and failure between components.
- [accessibility](plugins/birdiz-audit/skills/accessibility/SKILL.md): keyboard, names and
  roles, forms, contrast, reflow, against WCAG or RGAA, traced to templates.
- [seo](plugins/birdiz-audit/skills/seo/SKILL.md): indexability, crawl, duplicates, titles,
  structured data, rated for the documented production configuration.
- [performance](plugins/birdiz-audit/skills/performance/SKILL.md): server work per request,
  queries, remote calls, front-end loading, cost growing with data.
- [verify-findings](plugins/birdiz-audit/skills/verify-findings/SKILL.md): try to refute
  every finding from a context that did not write it.
- [remediation-plan](plugins/birdiz-audit/skills/remediation-plan/SKILL.md): group
  confirmed findings into fixes (one change, or the same files and
  executor), ordered, with who does each and what it waits for.
- [audit-report](plugins/birdiz-audit/skills/audit-report/SKILL.md): peer report,
  plain-language summary and remediation prompts, from verified findings.
- [tickets](plugins/birdiz-audit/skills/tickets/SKILL.md): one ticket per fix, following
  the target's conventions, in its tracker with the owner's permission
  (sensitive fixes only in an access-restricted one), local files
  otherwise; never edits a ticket once created.

A user-invoked skill may rely on model-invoked ones, never on another
user-invoked one.

**Review** (`birdiz-review`)

- [review-pr](plugins/birdiz-review/skills/review-pr/SKILL.md): one review
  run on a branch or a `base..head` range, written outside the repository:
  a bucket for every changed file (`must-read`, `glance`, `skim`,
  `unproven`), the coverage gaps and a proposed verdict (`merge`, `fix`,
  `close-and-reprompt`) with its round. Never writes to the reviewed branch.

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
- **Running the project is the owner's choice.** Off by default, never on a
  third party's code. See
  [ADR 0004](docs/adr/0004-execution-is-a-recorded-choice.md).
- **One set of findings, several reports.** Peer report, plain-language
  summary and remediation prompts are projections of the same findings.
- **One finding core.** The rules every finding follows, and the checks that
  read them, live once in [`core/`](core/finding_core/); the audit's
  validator and pointer checker extend it with the audit's axes, keys,
  sections and workspace layout.
- **One directory per plugin, each with its copy of the core.** Installing
  a plugin copies only its directory; `tools/sync_core.py` keeps every copy
  identical to `core/`, and CI fails on drift. See
  [ADR 0005](docs/adr/0005-two-plugins-share-a-copied-core.md).
- **A review never touches what it reviews.** No write to the reviewed
  branch, every coverage gap reported, and "safe to skim" only on detector
  evidence. See [ADR 0006](docs/adr/0006-review-invariants.md).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/projections-dark.svg">
  <img alt="One set of verified findings projected into a peer report, a summary and remediation prompts" src="docs/assets/projections-light.svg">
</picture>

Vocabulary is defined in [GLOSSARY.md](GLOSSARY.md); the visual identity in
[docs/brand.md](docs/brand.md).

## Develop

Edit the core in `core/` only, then copy it into the plugins and run the
tests (Python 3.11 or later, as CI does; the scripts also run on 3.8):

```
python3 -I tools/sync_core.py
python3 -I -m unittest discover -s tools -p 'test_*.py'
python3 -I -m unittest discover -s plugins/birdiz-audit/skills/finding-format/scripts -p 'test_*.py'
python3 -I -m unittest discover -s plugins/birdiz-review/skills/review-pr/scripts -p 'test_*.py'
```

Changes are listed in each plugin's changelog:
[birdiz-audit](plugins/birdiz-audit/CHANGELOG.md),
[birdiz-review](plugins/birdiz-review/CHANGELOG.md).

## Never commit an engagement

This repository holds skills only. Engagement workspaces contain confidential
findings and live elsewhere (`workspace_root` in the auditor profile).

## Roadmap

- Run `infra-security` and `privacy` against a cloud account (cloud read)

## License

MIT
