---
name: audit-kickoff
description: Frame one audit engagement by interview (target, scope, access, authorization, audience, deliverables) and create its workspace. Run once at the start of every audit.
disable-model-invocation: true
---

# audit-kickoff

Version: 0.14.0 (audit skills, see CHANGELOG)

Write the **engagement file**, everything true for this audit only, then run
the audit. Template, workspace and capability matrix:
[engagement-template.md](engagement-template.md).

Output: `<workspace_root>/<engagement-slug>/00-engagement.md`

## Process

1. **Profile.** Read `~/.config/audit-skills/profile.md`; missing: stop, ask
   the auditor to run `audit-setup`.
2. **Detect** from the repository or URL at hand: languages, frameworks,
   infrastructure as code, frontend, commit to audit, remote host and its
   issue tracker; for a running target, the commit and environment it
   serves, and the image it runs (built from which commit). Restate them in
   one block for confirmation.
3. **Interview in rounds.** Each round asks the frontier: the open questions
   whose prerequisites are settled, at most three, numbered, each with a
   recommended answer ("1 ok, 2 b, 3 ok"), through the structured question
   tool when there is one. Ask only what detection left open. When the
   auditor reads the forge or cloud with their own login, settle the scope
   of `cloud_read` here.
4. **Settle authorization.**
5. **Plan the axes** from the capability matrix.
6. **Create the workspace** outside the audited repository, and the
   dedicated clone at the audited commit inside it, recorded as
   `working_copy`.
7. **Read the file back**; explicit confirmation is recorded as `confirmed:
   <YYYY-MM-DD>` and is the go-ahead for the whole plan. For a third-party
   owner, give the auditor the questions of each planned axis that has a
   `questions.md` (`infra-security`, `privacy`), to send now: answers take
   time, and the axes refine them as they run.

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

## Amendment

An axis added after confirmation is an amendment: the auditor's request,
quoted with its date, under the axis plan, and the axis row added with its
status. Give its `questions.md` as at confirmation. The steps already run
keep their versions; the new ones record theirs.

## After confirmation

Run in order, without asking again:

1. `recon`, unless a map exists for the audited commit;
2. each axis `evaluated` or `partial`, in plan order, each in its own sub-agent
   when available; before the axes that need the running target, check again
   which commit it serves and which image runs it;
3. `verify-findings` in a context that wrote no finding (no sub-agents: tell
   the auditor to open a new session, and stop);
4. **answers** to the questions under `## Questions for the auditor`
   across the findings files:
   - *sort*: keep the questions whose answer could change a finding, a
     rating or an area's status, each with that effect in a few words; the
     others stay in the files, unasked;
   - *with a proposal*: one list per theme (production, personal data,
     intent...), each question in one line with its proposal; the owner
     accepts a list at once, or names the lines to change;
   - *without a proposal*, and the lines changed: asked one by one, as in
     the interview;
   - an answer an observation contradicts is asked again once, with the
     observation.

   The auditor, and the owner when present in the session (an
   auditor-owned target), answer now; questions for an absent owner go to
   the auditor as one list to send, the run continues without them, and a
   later session resumes here once answers are recorded. Each answer is
   recorded under its question (`finding-format`, Questions and answers);
5. a **lead pass** of each axis that received leads from verification or
   answers to its questions (`finding-format`, Lead pass), then
   `verify-findings` again on its new findings and on the confirmed
   findings it changed; one round only: leads and questions opened by
   either stay open, and reach the report as such;
6. copy into `tools` the skill versions and `name@version` each step listed
   in its output; a step that listed none is attributed the version it ran
   under, from `skills_version`, and said so;
7. `audit-report`; if it leaves a deliverable in DRAFT, the step its list
   names for each item (`verify-findings` in revision mode, a lead pass,
   this skill for the engagement file), then `audit-report` again.

Stop only for a **blocker**: an active step on an unauthorized host; a
required capability missing or unreachable; a contradiction with the file
(wrong commit, unclear scope). A missing accelerator (graph tool, scanner,
sub-agents) takes the skill's fallback, recorded (`method:`, `tools`), with
one line on what it costs; the auditor can rerun the step once it is back.
Steps communicate through files, so a new session can resume from the
workspace.

End by reporting what was produced, what was skipped and why, findings per
axis and severity, what was created on the target, and every question still
unanswered across the findings files, asked or not.
