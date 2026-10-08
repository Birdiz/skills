---
name: audit-kickoff
description: Frame one audit engagement by interview (target, scope, access, authorization, audience, deliverables) and create its workspace. Run once at the start of every audit.
disable-model-invocation: true
---

# audit-kickoff

Version: 0.6.0 (audit skills, see CHANGELOG)

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
   infrastructure-as-code, presence of a frontend, the commit to audit, the
   remote host and whether it has an issue tracker. If a running target is
   available, which commit and environment it serves.
2. **Interview in batches** (see "Asking questions"). Ask only what detection
   could not settle.
3. **Settle authorization** before going further (see "Authorization"). Never
   leave it pending.
4. **Derive the axis plan** from the capability matrix (table below).
5. **Create the workspace**, outside the client repository.
6. **Read the engagement file back** to the auditor and get an explicit
   confirmation before any axis runs. Record it as `confirmed: <YYYY-MM-DD>`.
7. **Carry on** (see "After confirmation"). The confirmation is the go-ahead
   for the whole plan; do not ask again whether to start.

## Asking questions

- Up to **three questions per message**, numbered, each with a recommended
  answer when one exists, so the auditor can reply "1 ok, 2 b, 3 ok".
- If the agent has a structured question tool (multiple choice), use it for
  the batch.
- Group only questions that do not depend on each other. A question whose
  answer decides which other questions are asked goes in an earlier batch.
- Restate detected facts in one block for confirmation; they are not
  questions.

Suggested batches:

| Batch | Questions |
|---|---|
| 1. Scope | target and out of scope; axes wanted; capabilities available |
| 2. Authorization | who owns the target; active testing wanted (only if a running target is available); authorization record |
| 3. Audience | readers; for self or client; who runs remediation prompts and in which language |
| 4. Tooling | confirm detected tools and MCP servers, and which are excluded |

## Questions

Each one has a consumer. If a new question is added, name the skill that
reads the answer.

| Question | Read by |
|---|---|
| What is the target, and what is explicitly out of scope? | all axes |
| Which capabilities are available: repository, running URL, cloud read access, answers from the client? | axis plan |
| Who owns the target: the auditor, or a third party? | authorization |
| Is active testing wanted, and on which hosts? | security axes |
| Who reads the result: a technical peer, a non-technical decision maker, or both? | reporting |
| Is the deliverable for the auditor or for a client? | reporting |
| Who will run the remediation prompts: a vendor, the client, the auditor? | remediation prompts |
| Which axes does the auditor want, if not all? | axis plan |
| Deliverable language, if different from the profile default? | reporting |
| Which third-party tools and MCP servers are active, and which are excluded? | engagement record |

## Authorization

Active testing needs an authorization from **the owner of the target**,
recorded in the engagement file. Who records it depends on who owns it.

**The auditor owns the target** (their own project, a local stack they
run). The auditor's explicit consent in the session is the authorization.
The agent writes the record itself, with:

- who authorized, and the date
- the hosts covered, which must be inside `in_scope`
- the auditor's statement, quoted verbatim

Ask for that statement directly ("Do you, as owner of `<target>`, authorize
active testing on `<hosts>`?"). A request for active tests made earlier in
the interview is a wish; the answer to this question is the authorization.

**A third party owns the target** (a client, an employer, a hosted service).
The auditor's consent does not authorize anything: they cannot grant access
to a system that is not theirs. Record a reference to the owner's written
authorization: document, date, signatory, scope. Without it, `testing:
passive`.

**Never leave it pending.** Before moving to the axis plan, authorization is
either recorded (`active`) or explicitly declined (`passive`, and the auditor
has been told what passive excludes). An engagement must not be confirmed
with an open authorization question.

## After confirmation

Run, in this order, without asking for permission between steps:

1. `recon`, unless `01-codebase-map.md` already exists for the audited
   commit.
2. Each axis of the plan with status `evaluated` or `partial`, in plan order.
3. `verify-findings`, in a context that did not write the findings (see that
   skill). Without sub-agents this means a new session: tell the auditor so,
   and stop there.
4. `audit-report`, once every finding has been through verification.

Stop and ask only for a **blocker**:

- a step needs authorization that is not recorded (an active test on a host
  not listed);
- a required capability turns out to be missing or unreachable (the running
  target is down, the repository cannot be read);
- something contradicts the engagement file (wrong commit, scope unclear).

An optional accelerator that is unavailable is **not** a blocker. If a graph
tool, a scanner or sub-agents are missing, use the fallback the skill
describes, record what was used in the output (`method:` in the codebase
map, `tools` in the engagement file), and say in one line what the absence
costs. The auditor can rerun a step later with the tool restored.

If the agent can spawn sub-agents, run each axis in its own, so one axis does
not fill the context of the next. Otherwise run them in sequence; every step
reads and writes files, so a new session can resume from the workspace at
any point.

At the end, report what was produced, what was skipped and why, the number
of findings per axis and severity, and every entry under `## Questions for
the auditor` across the findings files.

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
tools: [<name@version>]
mcp_servers: [<name@version>]
mcp_servers_excluded: [<name>]

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

**Passive by default.** `testing: active` requires the authorization fields
to be filled as described above. Reason: active testing without the owner's
authorization is a legal exposure for the auditor, not a preference.

**The workspace never lives inside the client repository.** Reason: findings
are confidential and must not reach client history or a public remote.

**Pin tool versions.** Record `name@version` for every tool and MCP server.
Reason: third-party tools run with the auditor's access on confidential code,
and the report must say what produced it.

**List excluded MCP servers.** Every connected server not used for the audit
is named in `mcp_servers_excluded`, and no code or finding is sent to it.
Reason: an agent with general-purpose connectors can move confidential
material out of the perimeter without anyone deciding to.
