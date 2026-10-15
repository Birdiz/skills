# Changelog

## 0.16.0 (unreleased)

From the first run of `remediation-plan` and the report on its plan (a copy
of the gn-platform 30edaa4 workspace, findings unchanged): 63 findings in 49
fixes (39 single, 1 one-change, 9 same-files), 15 quick wins, 9 fixes
waiting for a decision, no discrepancy; the report in DRAFT with five
blocking items, each routed to its owner, the 0.14.0 rules held (versions
no longer block). It caught a finding wrongly marked not sensitive, nine
findings changed by lead passes and never verified again, and a fix whose
check no longer failed before the fix. What was loose: two quick-win
definitions, same-files groups chaining from file to file, decisions named
without a question, mixed executors, staleness of the plan undefined.

- `remediation-plan`: what to read in the findings; when the plan is
  stale; same-files means the same place, with findings of one
  sensitivity; partial causes and shared consoles stay apart; a finding
  never split, options kept; executor is who does the main change, other
  steps named; what a fix waits for (undecided or deferred answers,
  decisions placed before the work), and a fix that is a decision; a check
  that still fails before the fix; `locations` where the change lands;
  three tiers in the order, first plan numbered in order; scripts and
  tools recorded; `**Grouping.**` for every fix
- `finding-format`: a quick win is a fix's property; an area waiting for an
  answer that could promote a lead, asked or not, is `partial`, while an
  answer deferring to someone else leaves nothing waiting
- `audit-report`: a finding changed after its note is not verified; a
  stale plan goes back; `sensitive` among blocking contradictions; a fix
  whose check passes without the fix blocks; fixers named in order; the
  recorded axis status shown beside the derived one; dated copies;
  questions waiting split three ways; top fixes from the plan's order

## 0.15.0 (unreleased)

Findings grouped into fixes, the unit of work the deliverables and the
coming tickets use. Auditor's decisions: findings share a fix when one
change resolves them, or when the same executor changes the same files in
one go; grouping is its own step, before the report; the report checks the
plan's form, and no independent verification checks the grouping, each
finding keeping its own check inside the fix.

- Add `remediation-plan`: every confirmed open finding in exactly one fix
  (`R-<NNN>`, `single`, `one-change` or `same-files`), each with why
  together, change, check, executor (`code`, `operations`, `owner`), effort
  and what it waits for (a fix or a decision); an order table; quick wins
  derived per fix; IDs stable across runs, fixes left empty kept as `done`
  or `dropped`; contradicting remediations kept apart as discrepancies; a
  script checks membership, derived fields and order
- `audit-report`: reads the plan, sends a missing or stale one back to
  `remediation-plan`, checks each fix against its findings (a dropped check
  or a contradicted remediation blocks); the peer report gains the plan,
  the summary's quick wins and the prompts are per fix
- `audit-kickoff`: `remediation-plan` runs after the second verification;
  `02-remediation-plan.md` in the workspace. Rules of engagement:
  `tool-output/plan/`

## 0.14.0 (unreleased)

From the first run of `infra-security` and `privacy` (a copy of the
gn-platform 30edaa4 workspace, the axes added by amendment, then
verification, the owner's answers, six lead passes, a second verification
and the report): 21 new findings, 21 confirmed, no rating changed by
verification, text corrected in 5; 63 confirmed in all; 29 of 31 questions
asked were answered; the report left in DRAFT. It also ran 0.12.0's lead
pass, cross-axis moves and verification resume for the first time. What
broke: questions due "before anything else" needed the inventory first; a
sub-agent axis could not ask; every lead pass had to break "changes nothing
else"; 31 questions took 11 rounds and the owner stopped; two recommended
answers were invented; an answer was contradicted by the forge's settings;
the stack ran a stale image under the audited code; a pull moved a tag a
running container used; fixture passwords reached an agent's context; the
report blocked on mixed skill versions with no route to fix them; scripts
of the copied workspace still pointed at the original.

Auditor's decisions: versions that differ between steps, each recorded or
attributed, do not block a report; confirmed findings a lead pass changed
are verified again; the answers step sorts questions, then offers proposals
as lists to accept at once.

- `finding-format`: the lead pass has a scope (close, apply answers, write
  the findings they reveal, open leads and questions, update the coverage it
  touched with a dated line) and what it changes is verified again. Lead
  statuses `closed: settled by F-…`, `closed: intended (Q-…)`, the declared
  form for facts as well as controls, joined forms for partial settlement;
  the shape of a bullet for another axis and of a moved lead. Questions
  carry a proposal from the repository, or none; older questions numbered;
  a sub-agent axis works on and says which answer moves a rating; answers
  keep the owner's words apart from the accepted proposal; an observation
  contradicting an answer is put to the owner once. `dynamic` covers forge
  and cloud settings; `locations` for a setting, an answer or an absence;
  `finding-format`'s sensitive cases win over an axis default;
  `## Created on target` in the section list
- Rules of engagement: the target is its code and its runtime image, checked
  against the audited commit; images pulled by digest, no tag a container
  uses moved, nothing retagged; `docker logs` filtered, the runtime may be
  queried for its settings, project commands may not, stores read only
  through the product; the cloud read scope (forge settings included) binds
  every step; credentials never printed; parallel active steps use separate
  accounts; later runs in their own `tool-output` subdirectory, paths
  relative to the workspace, times in UTC
- `audit-kickoff`: the image the target runs is detected and rechecked;
  `cloud_read` scope settled at the interview; amendment for an axis added
  after confirmation; the answers step sorts, lists proposals by theme,
  asks the rest one by one; the second verification covers changed
  findings; DRAFT items go to the step that owns each; steps that recorded
  no version are attributed one
- `verify-findings`: environment facts may be given; file by file;
  re-checks what an answer changed in a confirmed finding; checks the
  runtime image; note carries skill and tools; corrects a repeated fact in
  axis texts and plain language; rewrites a right closure's wrong reason,
  relabels closures resting on answers; moves any cross-axis bullet and
  closes one a confirmed finding covers; a rating depending on an answer is
  confirmed with its condition
- `audit-report`: versions recorded or attributed are provenance; an area
  status breaking the rule blocks; stale coverage, uncited compatible
  findings and a moved axis plan are cosmetic; undated URLs with a dated
  copy open; DRAFT items name who fixes them; declared facts from coverage
  listed with declared closures; asked and never-asked questions apart
- `infra-security`: boundaries with `app-security` (its server config,
  trusted proxies) and `code-quality` (merge checks); questions after the
  inventory; what `trivy config` does not read is read by hand, `zizmor`
  offline; build-stage files scanned at their stage, digests compared with
  today's, untagged means `latest`, when a CVE is a finding; image checked
  against the commit; no deploy job and no backup in IaC handled; unseen
  settings rated from the documented default. Grid: causes with no attacker
  in the middle column, resource limits as hardening
- `privacy`: legal applicability in doubt caps confidence at low, facts not
  shown stay leads; sources for the texts (Publications Office fallback,
  Légifrance, consolidated, dated twice) and how `references` name them;
  inventory lines `I-NN`; texts at the point of collection count as notice;
  browser on public pages then signed in, full URLs, dev cookies excluded;
  a processor not yet chosen; effort when a decision is awaited. Grid: a
  store holding some sensitive data counts, row for staff access
- `code-quality` grid: a delivery check that does not block a merge

## 0.13.0 (unreleased)

Two axes that rest partly on the owner's answers, in the same form (skill,
`areas.md`) plus a questionnaire (`questions.md`); neither has run yet. They
bring the declarative evidence regime into use, with the auditor's
decisions: development-only configuration is a finding rated for a
developer's machine; a control the owner declares without showing it closes
a lead as declared, not observed; answers are collected after verification,
then taken up by a lead pass.

- Add `infra-security`: an inventory of what defines the infrastructure and
  the deployment each file applies to; scanners as leads (`trivy config`,
  `hadolint`, `zizmor`); images, runtime and exposure, secrets delivery,
  pipeline, cloud through read-only access, backups and detection. The
  application's own code and configuration stay with `app-security`
- Add `privacy`: an inventory of personal data (enters, stored, read,
  leaves, deleted) every finding cites; the notice, legal bases and
  consent, the visitor's browser before any choice and after a refusal,
  third parties, rights, retention, records. The law is the owner's to
  state; not legal advice, a legal judgment caps confidence at medium.
  Exposure of personal data stays with the security axes
- `finding-format`: an answer is evidence of what the owner states, quoted
  with its question and date; a gap it reveals supports a finding, a control
  it claims closes a lead as declared; owner documents in `client-docs/`,
  masked. Answers recorded verbatim by whoever receives them, applied by the
  axis's lead pass. An area waiting for an answer is `partial`
- Rules of engagement: `docker ps` and `docker inspect` join read-only
  inspection, resolved values filtered out; an image the auditor built may
  be scanned; cloud read only through the owner's read-only access, store
  contents never read; one TLS handshake per host is passive, enumeration
  is active; personal data of real people recorded by field and location,
  never copied
- `audit-kickoff`: an answers step after verification (in rounds when the
  owner is in the session, a list to send otherwise), then the lead pass
  covers answers; questionnaires given to a third-party owner at
  confirmation; capability matrix for the two axes; `client-docs/` in the
  workspace
- `verify-findings`: checks a declarative finding against its recorded
  answer and the repository; spot-checks every lead closed as declared
- `audit-report`: declared, unobserved controls listed apart in the peer
  report
- `app-security` areas name their boundary with the two new axes;
  `audit-setup` detects `hadolint` and `zizmor`

## 0.12.0 (unreleased)

From the first full run (gn-platform at a new commit: kickoff, recon, six
axes in parallel against a local dev stack, verification, report): 42
findings, 42 confirmed, no rating changed, text corrected in 7; the report
out of draft with six cosmetic discrepancies. What broke: a lead one axis
wrote into another's file was lost when that axis rewrote its file, two
axes picked the same lead ID, three leads went to axes that had already run
and nobody owned them; the verification was cut by a network error; dev
tools filled a crawl and polluted scans; a report kept a session cookie;
no step recorded its own skill version.

- `finding-format`: axes write only in their own file; leads for other
  axes go under `## Leads for other axes`, and `verify-findings` moves and
  numbers them; an axis that receives leads after it ran does a lead pass.
  One status form for a lead settled in part. Questions numbered
  `Q-<AXIS>-<NN>` and asked once. Facts about a given account (existence,
  state) are sensitive. Axis status derived from its areas; coverage opens
  with the skill version
- Rules of engagement (auditor's decisions): under active, a step may create
  data through the product's forms with the auditor's test accounts, listed,
  never deleting; a container the auditor runs may be read with
  `docker exec`, environment variables by name only. Also: one browser
  context per step; development tools excluded from crawls, scans and
  measurements; files holding secrets read through a mask, credentials
  removed from tool reports; installs and caches in `<workspace>/cache/`; a
  run that read nothing is not a clean result; `tool-output/report/`
- `verify-findings`: resumes past findings already verified; rechecks the
  commit served and data drift before replaying; quotes must be at their
  pointer and counts match what they claim; adds missing citations between
  findings with one cause; moves cross-axis leads, rewrites settled ones,
  lists the axes needing a lead pass
- `audit-kickoff`: creates the dedicated clone; rechecks the served commit
  before dynamic axes; lead pass and second verification; copies tools and
  skill versions before the report; runs the draft loop
- `audit-report`: counts scripted; blocking discrepancies widened (an
  incomplete remediation, a claim contradicted by its own text or note,
  findings with one cause at odds); edits no findings file; linked findings
  grouped in the summary; one coverage table; questions by ID with their
  effect on counts
- `recon`: one dependency line per ecosystem, tooling-only ecosystems not
  installed; main flows list their pages; map pointers unquoted; only
  relied-on edges checked; graph registries outside the workspace recorded
- Axes: `app-security` falls back to a vulnerability database where the
  audit command runs the project, and rates victim-action weaknesses one
  level lower; `code-quality` may confirm a defect on the target, grid rows
  for broken business rules and leftovers; `architecture` defines when a
  flow counts and who the team is; `accessibility` cites WCAG 2.2 under RGAA
  where RGAA lacks the criterion, skip link under RGAA, set-level criteria
  never on one page; `seo` derives the indexing proposal from the code,
  dates its references, marks deductions from a dev target, grid rows for
  thin content and ineligible enhancements; `performance` paces and warms
  measurements, lowers dev-only measurements one level, does not count
  bounded growth

## 0.11.0 (unreleased)

Three dynamic axes, in the same form (skill plus `areas.md`); none has run
yet.

- Add `accessibility`: a sample of pages (main flows, one per template), an
  automated pass whose results are leads, then the keyboard, the
  accessibility tree, forms and visual checks by hand, each problem traced to
  its template. WCAG or RGAA from the profile; a legal obligation is the
  owner's to state, and raises one level
- Add `seo`: a rate-limited crawl, robots and sitemaps against it, served
  against rendered HTML, routes no link reaches. Rated for the documented
  production configuration; which pages should be indexed is the owner's
  intent, proposed from the map and asked up front
- Add `performance`: server work per request read in the code, single-request
  measurements and Lighthouse medians, growth with data. A measurement
  stands alone only on a production-like configuration; expected volumes are
  asked up front
- Rules of engagement: signing in with an account the auditor provides is
  ordinary use; forms are submitted only to show validation (passive) or on
  the auditor's own data (active); crawls are sequential, one request per
  second at most, capped; no load or stress test in any regime

## 0.10.0 (unreleased)

From the 0.9.0 rerun of `code-quality` and `architecture` (fresh copy of the
gn-platform workspace, then `verify-findings`): 7 findings, 7 confirmed, no
rating changed, text corrected in 6. The 0.9.0 rules held: `L-SEC-21` closed
as settled, the performance lead moved, the engagement file untouched, the
same problems found. New: a shell hook truncated `git log` and `grep` output
without saying so; an identical lockfile sat over an incomplete install; the
two grids rated the same race differently; the two axes diverged on a
weakness the owner documents as planned work.

- Rules of engagement: counts and lists cited as evidence come from a script
  run with `bash`; an install is used only if its record of installed
  packages lists every locked one; a map without `dependencies:` leaves the
  search to the step, recorded; tool runs go in `tool-output/<step>/`; a
  pinned base image may carry a tool without its own image; another clone's
  graph index at the same commit may be queried, and said
- `finding-format`: the rare-precondition and planned-change moves apply to
  every grid; a weakness the owner documents as a known limit or planned
  work is still a finding, citing the document, level kept; partial
  settlement (`settles L-… (part: …)`); `references` may be empty; questions
  may concern a coverage area and go in the file at once when asked up
  front; area names and status words stay in English
- `verify-findings`: looks for the owner's known limits and planned work;
  corrects a fixed fact where the coverage repeats it, annotates questions
  the repository answers; rewrites partially settled leads
- `code-quality`: the CI question goes in a new findings file first; fix
  commits by subject with the exact command; under three months, review
  rounds are one change and a hotspot only supports a finding; grid row for
  what misleads a reader replaces the hygiene row; only copies whose
  behaviour differs are diverged
- `architecture`: "structural Unknown" defined, leads closed before
  finishing, those already another axis's finding closed with its ID; leads
  to any other axis, in-plan ones included; a deliberate layout is a force;
  "most main flows" is more than half
- `recon`: an existing install is checked for completeness, not only its
  lockfile

## 0.9.0 (unreleased)

From the first run of `code-quality` and `architecture` (gn-platform, same
commit and map as the first engagement, axes in parallel sub-agents, then
`verify-findings`): 8 findings, 8 confirmed, no rating changed, text
corrected in 4. Twice a new axis settled an open `app-security` lead that
stayed open in its file; a performance lead was closed instead of moved; two
reasons for a severity move were wrong while the move held; both axes wrote
the engagement file at the same time.

- `finding-format`: one problem stays in one axis. A consequence for another
  axis is appended there as a lead, even outside the plan; a finding that
  settles another axis's lead names it; findings with one cause cite each
  other. What was examined and dropped is a coverage note, not a lead
- `finding-format`: pointers quote a few words of their line; "shown" means
  every step pointed, one reasoned step caps confidence at medium; a severity
  move gives its reason with a pointer; a system not yet in production is
  rated for its documented deployment; `evidence_regime` defined
- `verify-findings`: closes the leads that confirmed findings settle, in
  their own file; checks the reason of a severity move, not only the move;
  moves a lead closed although it belonged to another axis; a cost the audit
  itself met counts when any newcomer would meet it
- Rules of engagement: a tool an axis names runs from a pinned image when the
  profile lists `docker`; read-only host commands are allowed; dependency
  code is read where the map says, lockfile rechecked; rules and scripts
  written for a run are kept; each step lists its tools in its own output
  and only `audit-kickoff` writes them to the engagement file
- `code-quality`: CI merge-blocking asked up front; whole history when
  shorter than twelve months, merges excluded, fix commits by subject; under
  three months, a hotspot needs reworked code; grid read where the wrong
  result reaches a user, a rare precondition lowers one level
- `architecture`: the map's departures and structural unknowns become leads
  first; coarse modules split and said; coupling without merges, three
  commits or more, supporting only under three months of history; grid row
  for gaps that delay diagnosis or a decision; an unnoticed failure is an
  outage of what it carries; plans in the repository count for raising a
  level
- `recon`: `tools:` in the map header. `audit-setup`: detects `docker` as the
  way to run named tools

## 0.8.0 (unreleased)

Rewritten for brevity, following mattpocock/skills `writing-for-agents`. No
behaviour change intended; file formats unchanged. 7 678 words to about
4 950, sibling files included; the rest is mostly file templates, kept as
they are.

- History and justifications moved out of the skills (this file and the ADRs
  keep them); each rule stated once, in the affirmative
- Reference moved to sibling files reached by a link:
  `audit-kickoff/engagement-template.md` (template, workspace, capability
  matrix), `finding-format/schema.md` (finding layout, IDs, lead bullet,
  severity scale), `app-security/areas.md` (areas, severity grid),
  `audit-report/deliverables.md` (peer report, summary, prompts)
- `finding-format/rules-of-engagement.md`: the single home of what an audit
  may touch and run (read-only repository, no execution, passive and active
  regimes, secrets, scripted tool runs, excluded artifacts), formerly spread
  across `recon`, `app-security` and `verify-findings`
- `audit-setup`, `audit-kickoff`: interviews in rounds over the frontier, at
  most three questions each; the question table becomes a field-to-reader
  line in the engagement template
- `finding-format` description names the rules of engagement, so steps that
  need them reach the skill
- Leading words: rules of engagement, projection, refute, blocker, draft

Regression on the first engagement (same post-recon input, `app-security`
run with 0.8.0 and with 0.7.0 as a control): both versions find the same
seven weaknesses and miss the same ones; verification, an auditor answer,
the draft and revision loop behave as before. Fixes from the run:

- The secret rule is stated in the rules of engagement for every workspace
  file, default and placeholder values included, and recalled where
  findings are written; with the rule behind a link only, a run quoted a
  secret
- `finding-format`: the framework text is fetched into `tool-output/` before
  a reference is cited
- `app-security`: the passive regime is recalled where the running target is
  handled; behind a link only, a run requested a path it had composed. Every
  cited identifier, CWE included, comes from the framework text

New axes, written in the same form (skill plus `areas.md` with the areas and
the severity grid); neither has run on a real codebase yet:

- Add `code-quality`: defects on the main flows, error handling, hotspots
  from history and complexity, duplication, tests read but not run,
  consistency with the project's own rules. A finding names a cost shown in
  this codebase, never a preference
- Add `architecture`: real dependency graph against the documented one,
  change coupling from history, data ownership, consistency and failure
  between components, third-party coupling, operability. Judged against the
  system's forces, never against a style; fixes needing a decision are not
  promptable
- Rules of engagement: an analyser whose project configuration is code runs
  only with a configuration the auditor wrote; `git log` commands are
  scripted like scanner runs
- `verify-findings`: for these two axes, refute a claimed cost that is a
  preference
- `audit-setup`: detect `lizard`, `scc` and `jscpd`

## 0.7.0 (unreleased)

- Ship as a Claude Code plugin (`birdiz-skills`) through a marketplace in
  this repository

From the second report run: the draft mechanism worked (ten discrepancies
down to four, accepted findings in their own section, skill versions
checked), but kept the report in draft over cosmetic issues and over a rule
that could not be satisfied.

- `audit-report`: discrepancies are blocking (what a reader acts on is wrong
  or unreadable) or cosmetic (form only); only blocking ones keep a
  deliverable in draft
- `finding-format`: leads of an axis outside the plan carry `open: axis not
  requested`; answer labels stay in English; an answer can change
  `promptable`
- `recon`: same status for leads outside the plan, written in the engagement
  language

## 0.6.0 (unreleased)

From the first report run. The report listed ten discrepancies between the
findings and their verification notes, written before 0.4.0, and the owner's
answers had changed two findings with no rule for it.

- `finding-format`: new `resolution` key (`open`, `accepted`, `fixed`),
  independent of `status`; quick wins require `open`. How a session records
  an auditor's answer and applies its consequences
- `verify-findings`: revision mode, to apply listed discrepancies to findings
  already verified
- `audit-report`: consistency check before writing; deliverables marked DRAFT
  while discrepancies remain, then handed to `verify-findings` and
  regenerated; accepted findings in their own section; skill versions
  actually used in the provenance

## 0.5.0 (unreleased)

- Add `audit-report`: peer report, plain-language summary and remediation
  prompts, chosen from the engagement's audience. A projection of the
  findings: no new analysis, counts recomputed, stops when verification is
  missing. Sensitive findings reach the summary by consequence only; prompts
  describe the target state and never the attack
- `audit-kickoff` and `verify-findings` hand over to `audit-report`

## 0.4.0 (unreleased)

From the first verification run (11 findings: 11 confirmed, 0 refuted, 10
corrected).

- `verify-findings`: corrects in place what it proved wrong, quoting the old
  text in its note, so reports never carry a known error; a rating change
  must give its reason and update every sentence stating the old rating;
  passive means no guessed URLs or identifiers
- `finding-format`: `sensitive` asks whether the finding helps an outside
  attacker; weaknesses only a legitimate privileged user can exercise are not
  sensitive. A reference must state what the finding says is missing; a
  versioned URL is enough. Old keys (`impact`) are ignored
- `app-security`: guessed identifiers are not passive

## 0.3.0 (unreleased)

- Add `verify-findings`: the only step that confirms or refutes a finding,
  run in a context that did not write it, trying to refute rather than
  confirm. Adds a `verification` key and paragraph to every finding,
  spot-checks closed leads, writes no new findings
- `audit-kickoff`: runs `verify-findings` after the axes, or tells the
  auditor to open a new session when there are no sub-agents
- `finding-format`: status changes belong to `verify-findings`

## 0.2.0 (unreleased)

From the first real engagement (a self-audit, `app-security` only).

- Every skill carries a `Version:` line, so an engagement records which
  version produced it even when installed without this repository
- `finding-format`: remove `impact` (it duplicated severity); quick win is now
  confirmed, severity medium or above, effort S. Leads get IDs and a check,
  and the owning axis closes each one. New coverage status `not-requested`.
  New section for questions to the auditor. English headings and keys, prose
  in the engagement language. Cite only what a reader can open; check
  framework references against their source. Publicly observable findings
  are not sensitive
- `recon`: graph edges can be wrong and are verified; dependency source from
  an identical install or an install without scripts; unknowns say who can
  settle them; leads stay short; leads for axes outside the plan are kept
- `app-security`: severity grid recalibrated, with an availability row;
  scanner runs scripted and kept; the auditor's own artifacts excluded from
  scans; owner instructions for agents are not injection; running target
  checked against the audited commit; every lead closed
- `app-security`: align the `sensitive` rule and dependency reading with
  `finding-format` and `recon`
- `audit-kickoff`: records the working copy and what the running target
  serves; end report lists the questions for the auditor

## 0.1.0 (unreleased)

- Add `audit-setup`, `audit-kickoff`, `finding-format`, `recon`
- Add `app-security`, the first audit axis
- `audit-kickoff`: ask questions in batches of up to three; record the
  auditor's own authorization for targets they own; never confirm an
  engagement with authorization pending; list excluded MCP servers
- `audit-kickoff`: after confirmation, run `recon` and the planned axes
  without asking again; stop only for blockers, not for missing optional
  tools
- `audit-setup`: ask questions in batches
- `app-security`: a running target provided by the auditor is not
  "executing the project"; active tests limited to authorized hosts
- Add glossary (`CONTEXT.md`) and ADRs 0001 to 0003
