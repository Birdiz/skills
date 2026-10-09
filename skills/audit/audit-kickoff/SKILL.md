---
name: audit-kickoff
description: Frame one audit engagement by interview (target, scope, access, authorization, audience, deliverables) and create its workspace. Run once at the start of every audit.
disable-model-invocation: true
---

# audit-kickoff

Version: 0.10.0 (audit skills, see CHANGELOG)

Write the **engagement file**, everything true for this audit only, then run
the audit. Template, workspace and capability matrix:
[engagement-template.md](engagement-template.md).

Output: `<workspace_root>/<engagement-slug>/00-engagement.md`

## Process

1. **Profile.** Read `~/.config/audit-skills/profile.md`; missing: stop, ask
   the auditor to run `audit-setup`.
2. **Detect** from the repository or URL at hand: languages, frameworks,
   infrastructure as code, frontend, commit to audit, remote host and its
   issue tracker; for a running target, the commit and environment it serves.
   Restate them in one block for confirmation.
3. **Interview in rounds.** Each round asks the frontier: the open questions
   whose prerequisites are settled, at most three, numbered, each with a
   recommended answer ("1 ok, 2 b, 3 ok"), through the structured question
   tool when there is one. Ask only what detection left open.
4. **Settle authorization.**
5. **Plan the axes** from the capability matrix.
6. **Create the workspace** outside the audited repository.
7. **Read the file back**; explicit confirmation is recorded as `confirmed:
   <YYYY-MM-DD>` and is the go-ahead for the whole plan.

## Authorization

Active testing needs the target owner's authorization, in the file.

- **Auditor-owned target** (their project, a stack they run): ask "Do you, as
  owner of `<target>`, authorize active testing on `<hosts>`?". That answer,
  quoted verbatim with who, when and hosts inside `in_scope`, is the
  authorization, written by the agent; an earlier wish for active tests is not.
- **Third-party target**: only the owner's written authorization counts:
  document, date, signatory, scope. Without it, `testing: passive`.

Settle it before the axis plan: `active` with its record, or `passive` with
the auditor told what passive excludes. Confirmation waits until it is
settled.

## After confirmation

Run in order, without asking again:

1. `recon`, unless a map exists for the audited commit;
2. each axis `evaluated` or `partial`, in plan order, each in its own sub-agent
   when available;
3. `verify-findings` in a context that wrote no finding (no sub-agents: tell
   the auditor to open a new session, and stop);
4. `audit-report`.

Stop only for a **blocker**: an active step on an unauthorized host; a
required capability missing or unreachable; a contradiction with the file
(wrong commit, unclear scope). A missing accelerator (graph tool, scanner,
sub-agents) takes the skill's fallback, recorded (`method:`, `tools`), with
one line on what it costs; the auditor can rerun the step once it is back.
Steps communicate through files, so a new session can resume from the
workspace.

End by copying into `tools` the `name@version` each step listed in its
output, then report what was produced, what was skipped and why, findings
per axis and severity, and every entry under `## Questions for the auditor`
across the findings files.
