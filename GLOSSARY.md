# Context

Shared vocabulary for these skills. Use these terms as defined, in skills,
findings and reports.

- **Auditor profile**: what is stable for one auditor across audits (agent,
  tools, severity scale, language). Written by `audit-setup`.
- **Engagement**: one audit of one target for one audience. Described by the
  engagement file, written by `audit-kickoff`.
- **Workspace**: the directory holding one engagement's files. Never inside
  the audited repository, never inside this one.
- **Capability**: a kind of access available for an engagement: repository,
  running URL, cloud read access, client answers.
- **Axis**: one dimension of the audit (app security, accessibility, ...).
  One axis, one findings file.
- **Evidence regime**: how an axis can prove something. *Static* (the
  repository is enough), *dynamic* (needs a running target), *declarative*
  (needs answers from the client).
- **Declared**: what rests only on the owner's answer. An answer that
  reveals a gap supports a declarative finding; one that claims a control
  closes a lead as declared, not observed, and the reports list it apart.
- **Lead pass**: an axis taking up, after it ran, the leads moved into its
  file and the answers to its questions; it touches only what they
  concern, and what it changes is verified again.
- **Proposal**: the answer the repository suggests to a question, with its
  pointer; the owner accepts or corrects it. A fact only the owner knows
  has none.
- **Codebase map**: the shared description of the audited code, written once
  by `recon` and read by every axis.
- **Finding**: an observed, evidenced problem in the common schema.
- **Lead**: a suspicion without evidence. Not reportable as a finding. The
  owning axis closes each one: promoted, closed, or open.
- **Coverage**: what an axis evaluated, partially evaluated, could not
  evaluate, or was not asked to evaluate.
- **Fix**: one piece of work (a pull request, a session in a console, a
  decision) resolving one or more confirmed findings, `R-<NNN>`; its
  findings share one change, or the same files and executor.
- **Remediation plan**: the ordered fixes of an engagement, with who does
  each and what it waits for. Written by `remediation-plan`.
- **Ticket**: one fix handed to whoever does it, in the target's issue
  tracker when the owner allows it, a local file otherwise; drawn from the
  fix, never carrying how the problem is exploited, and the team's once
  created. Written by `tickets`.
- **Quick win**: an open fix of medium severity or above, small effort,
  waiting for nothing. Derived, not stored.
- **Resolution**: what the owner did about a finding: open, accepted (kept by
  decision), or fixed (verified at a later commit). Independent of status.
- **Sensitive**: a finding that would help an outside attacker or expose
  personal data if leaked. Confidential report only.
- **Promptable**: a finding whose remediation a coding agent could apply.
- **Invariant**: a rule no setting can turn off.
- **Rules of engagement**: what an audit step may touch and run: read-only
  repository, no execution of the project unless its owner allows it on their
  own target, passive by default, active only on authorized hosts.
- **Execution**: what the engagement lets an agent run of the project: nothing
  (`none`), its tests in a throwaway copy (`disposable-copy`), or also the
  target (`local-target`). More than `none` only on the auditor's own target.
- **Exposure**: who uses the target today. Recorded at kickoff; it lowers no
  rating.
- **Priority**: an owner's decision to do a fix before a planned change it
  does not block. It orders the plan and leaves severity alone.
- **Holding item**: a report problem that can change only one low-severity
  fix nothing else waits for. It holds that fix, without a DRAFT.
- **Reservation**: what still blocks after the round that follows a DRAFT.
  The report is final, says so at the top, and the fixes concerned stay held.
- **Projection**: a deliverable derived from the findings files alone; it adds
  no analysis and is regenerated, never edited, when they change.
- **Peer report**: the complete, confidential deliverable for a technical
  reader.
- **Summary**: the plain-language deliverable for a decision maker; confirmed
  findings only, sensitive ones by consequence only.
- **Remediation prompt**: a self-contained instruction for a coding agent or
  a developer, describing the target state, never the attack.
