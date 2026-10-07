---
name: audit-kickoff
description: Frame one audit engagement by interview (target, scope, access, authorization, audience, deliverables) and create its workspace. Run once at the start of every audit.
disable-model-invocation: true
---

# audit-kickoff

Create the **engagement file**: everything that is true for this audit only.
Every other audit skill reads it and refuses to run without it.

Output: `<workspace_root>/<engagement-slug>/00-engagement.md`

## Before starting

Read the auditor profile at `~/.config/audit-skills/profile.md`. If it is
missing, stop and ask the auditor to run `audit-setup`. Do not assume
defaults.

## Process

1. **Detect before asking.** If a repository or URL is already at hand,
   inspect it and record: languages and frameworks, presence of
   infrastructure-as-code, presence of a frontend, the commit to audit.
2. **Interview**, one question at a time. Give a recommended answer when one
   exists. Ask only what detection could not settle.
3. **Derive the axis plan** from the capability matrix (table below).
4. **Create the workspace**, outside the client repository.
5. **Read the engagement file back** to the auditor and get an explicit
   confirmation before any axis runs.

## Questions

Each one has a consumer. If a new question is added, name the skill that
reads the answer.

| Question | Read by |
|---|---|
| What is the target, and what is explicitly out of scope? | all axes |
| Which capabilities are available: repository, running URL, cloud read access, answers from the client? | axis plan |
| Is any active testing authorized, and where is the written authorization? | security axes |
| Who reads the result: a technical peer, a non-technical decision maker, or both? | reporting |
| Is the deliverable for the auditor or for a client? | reporting |
| Who will run the remediation prompts: a vendor, the client, the auditor? | remediation prompts |
| Which axes does the auditor want, if not all? | axis plan |
| Deliverable language, if different from the profile default? | reporting |
| Which third-party tools and MCP servers are active for this engagement? | engagement record |

## Capability matrix

An axis runs only at the level its capabilities allow.

| Axis | Repository | Running URL | Cloud read | Client answers |
|---|---|---|---|---|
| code-quality | required | | | |
| architecture | required | | | |
| app-security | required | improves | | |
| infra-security | required (IaC) | | improves | |
| privacy | improves | improves | | required |
| accessibility | improves | required | | |
| seo | improves | required | | |
| performance | improves | required | | |

- All required capabilities present: `evaluated`.
- Only "improves" capabilities present: `partial`, and the engagement file
  says what is missing.
- A required capability missing: `not-evaluable`. The axis is listed in the
  plan with that status, so the gap reaches the report.

## Engagement file template

```markdown
# Engagement: <name>
created: <YYYY-MM-DD>
skills_version: <version from CHANGELOG>

## Target
description: <one paragraph>
repository: <path or URL | none>
commit: <sha | n/a>
url: <URL | none>
in_scope: [<list>]
out_of_scope: [<list>]

## Capabilities
repository: <yes|no>
running_url: <yes|no>
cloud_read: <yes|no>
client_answers: <yes|no, contact>

## Authorization
testing: <passive|active>
authorization_ref: <document, date, signatory | n/a>

## Audience
readers: <peer|non-technical|both>
for: <self|client>
prompt_executor: <vendor-brief|executable|both|none>
language: <fr|en|...>

## Tooling
tools: [<name@version>]
mcp_servers: [<name@version>]

## Axis plan
| Axis | Status | Missing |
|---|---|---|
| ... | evaluated/partial/not-evaluable | ... |
```

## Workspace

```
<engagement-slug>/
  00-engagement.md
  01-codebase-map.md     # written by recon
  findings/              # one file per axis
  reports/
```

## Rules

**Passive by default.** `testing: active` requires `authorization_ref` to be
filled. Without it, write `passive`, whatever the auditor says verbally.
Reason: active testing without written authorization is a legal exposure for
the auditor, not a preference.

**The workspace never lives inside the client repository.** Reason: findings
are confidential and must not reach client history or a public remote.

**Pin tool versions.** Record `name@version` for every tool and MCP server.
Reason: third-party tools run with the auditor's access on confidential code,
and the report must say what produced it.
