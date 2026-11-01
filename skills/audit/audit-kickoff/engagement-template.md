# Engagement file

Ask only for fields with a reader: target and scope (all axes), owner
(authorization), capabilities and wanted axes (axis plan), testing and hosts
(security axes; asked only with a running target), audience (`audit-report`),
tickets (`tickets`; the tracker fields only with a tracker), tools and MCP
servers (record, provenance), exposure (proposals, inventories; it lowers no
rating, `finding-format`, Rating), execution (`audit-kickoff`, Execution),
depth and focus (what the axis stresses, in the auditor's words).
Tools are pinned `name@version`;
every connected MCP server left unused goes in `mcp_servers_excluded` and
receives no code or finding. A browser tool the plan needs for a running URL
stays out of it, and acts on the target as the rules of engagement allow.

```markdown
# Engagement: <name>
created: <YYYY-MM-DD>
confirmed: <YYYY-MM-DD | pending>
skills_version: <the "Version:" line of the audit skills used>

## Target
description: <one paragraph>
owner: <auditor|third party: name>
repository: <path or URL | none>
working_copy: <path of the dedicated clone, created with the workspace>
commit: <sha | n/a>
url: <URL | none>
url_serves: <commit and environment the running target serves, and who runs it: the auditor, or each step under `execution: local-target` | n/a>
in_scope: [<list>]
out_of_scope: [<list>]

## Exposure
users_today: <nobody | the owner alone, online or not | testers: how many | public>
accounts: <how many, whose>
third_party_data: <none | what, whose>
opens: <YYYY-MM-DD | not planned | already open>

## Capabilities
repository: <yes|no>
running_url: <yes|no>
cloud_read: <yes|no>
client_answers: <yes|no, contact>

## Authorization
testing: <passive|active>
hosts: [<list> | n/a]
authorized_by: <name, role | n/a>
authorized_on: <YYYY-MM-DD | n/a>
evidence: <"verbatim statement" (auditor-owned) | document reference (third party) | n/a>
execution: <none|disposable-copy|local-target>
execution_by: <"verbatim statement", who, YYYY-MM-DD | n/a>

## Audience
readers: <peer|non-technical|both>
for: <self|client>
prompt_executor: <vendor-brief|executable|both|none>
prompts_scope: <quick-wins|all-promptable | n/a>
language: <fr|en|...>

## Tickets
destination: <tracker|local>
tracker: <kind (github, gitlab, forgejo, jira...): project | none>
visibility: <restricted|public|unknown, from its API on YYYY-MM-DD>
allowed_by: <name, role | n/a>
allowed_on: <YYYY-MM-DD | n/a>
evidence: <"verbatim statement" (auditor-owned) | document reference (third party) | n/a>
conventions: <repository path of its ticket conventions | none>
labels: [<existing label>: <when it applies>; <existing label>: <when>]

## Tooling
tools: [<name@version>]   # copied <YYYY-MM-DD> from each step's output
skills_by_step: [<step (date): name@version>]   # copied with tools
mcp_servers: [<name@version>]
mcp_servers_excluded: [<name>]

## Axis plan
| Axis | Status | Depth | Focus | Missing |
|---|---|---|---|---|
| ... | evaluated/partial/not-evaluable | full/light | ... | ... |
```

## Workspace

Outside the audited repository, so findings reach neither its history nor its
remote:

```
<engagement-slug>/
  00-engagement.md
  01-codebase-map.md     # recon
  02-remediation-plan.md # remediation-plan
  findings/              # one file per axis
  tickets/               # tickets, one per fix, and their index
  client-docs/           # documents the owner gives, masked
  reports/
```

## Capability matrix

- **Required**: repository for code-quality, architecture, app-security;
  repository with infrastructure as code, or cloud read, for
  infra-security; running URL for accessibility, seo, performance; client
  answers for privacy.
- **Improves**: running URL for app-security, infra-security and privacy;
  cloud read and client answers for infra-security; repository for privacy,
  accessibility, seo, performance.

All required present: `evaluated`. Only improving ones present: `partial`,
with what is missing. A required one missing: `not-evaluable`, kept in the
plan so the gap reaches the report.
