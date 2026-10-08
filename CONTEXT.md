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
- **Codebase map**: the shared description of the audited code, written once
  by `recon` and read by every axis.
- **Finding**: an observed, evidenced problem in the common schema.
- **Lead**: a suspicion without evidence. Not reportable as a finding. The
  owning axis closes each one: promoted, closed, or open.
- **Coverage**: what an axis evaluated, partially evaluated, could not
  evaluate, or was not asked to evaluate.
- **Quick win**: a confirmed finding of medium severity or above and small
  effort. Derived, not stored.
- **Sensitive**: a finding that would help an outside attacker or expose
  personal data if leaked. Confidential report only.
- **Promptable**: a finding whose remediation a coding agent could apply.
- **Invariant**: a rule no setting can turn off.
- **Peer report**: the complete, confidential deliverable for a technical
  reader.
- **Summary**: the plain-language deliverable for a decision maker; confirmed
  findings only, sensitive ones by consequence only.
- **Remediation prompt**: a self-contained instruction for a coding agent or
  a developer, describing the target state, never the attack.
