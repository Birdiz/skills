# Engagement file

Ask only for fields with a reader: target and scope (all axes), owner
(authorization), capabilities and wanted axes (axis plan), testing and hosts
(security axes; asked only with a running target), audience (`audit-report`),
tools and MCP servers (record, provenance). Tools are pinned `name@version`;
every connected MCP server left unused goes in `mcp_servers_excluded` and
receives no code or finding.

```markdown
# Engagement: <name>
created: <YYYY-MM-DD>
confirmed: <YYYY-MM-DD | pending>
skills_version: <the "Version:" line of the audit skills used>

## Target
description: <one paragraph>
owner: <auditor|third party: name>
repository: <path or URL | none>
working_copy: <path of the dedicated clone, set by recon>
commit: <sha | n/a>
url: <URL | none>
url_serves: <commit and environment the running target serves | n/a>
in_scope: [<list>]
out_of_scope: [<list>]

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

## Audience
readers: <peer|non-technical|both>
for: <self|client>
prompt_executor: <vendor-brief|executable|both|none>
language: <fr|en|...>

## Tooling
tools: [<name@version>]   # copied at the end from each step's output
mcp_servers: [<name@version>]
mcp_servers_excluded: [<name>]

## Axis plan
| Axis | Status | Missing |
|---|---|---|
| ... | evaluated/partial/not-evaluable | ... |
```

## Workspace

Outside the audited repository, so findings reach neither its history nor its
remote:

```
<engagement-slug>/
  00-engagement.md
  01-codebase-map.md     # recon
  findings/              # one file per axis
  reports/
```

## Capability matrix

- **Required**: repository for code-quality, architecture, app-security,
  infra-security (IaC); running URL for accessibility, seo, performance;
  client answers for privacy.
- **Improves**: running URL for app-security and privacy; cloud read for
  infra-security; repository for privacy, accessibility, seo, performance.

All required present: `evaluated`. Only improving ones present: `partial`,
with what is missing. A required one missing: `not-evaluable`, kept in the
plan so the gap reaches the report.
