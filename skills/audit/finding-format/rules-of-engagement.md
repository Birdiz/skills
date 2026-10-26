# Rules of engagement

Binding on every audit step: recon, axes, verification.

- The audited repository stays byte-identical; indexes, caches and tool output
  live in the dedicated clone or the workspace.
- What runs: analysis tools reading the code, the no-scripts dependency install
  `recon` describes, requests to the target. The project itself never runs
  (install scripts, build, tests, containers), and the agent starts no target.
  A target the auditor runs or provides (a local stack, a staging URL) may be
  observed and tested.
- A tool an axis skill names runs when the profile lists it, or, when the
  profile lists `docker`, from an image pinned by digest (a pinned base image
  with the tool installed at a pinned version, when the tool has no image).
  Read-only commands on the working copy (`git log`, a script reading files,
  graph tool queries) run on the host; a graph index built from another clone
  at the same commit may be queried, and the output says so.
- An analyser whose project configuration is code (`eslint.config.js`, a
  PHPStan `bootstrap`, a `conftest.py`, a build plugin) runs that code: run it
  with a configuration you wrote that loads nothing from the project, or ask
  the auditor to run the project's own and paste the output.
- Dependency code is read where the map's `dependencies:` line says, inside
  the workspace or not. An existing install is used only while its lockfile
  stays byte-identical to the audited one (`cmp`) and its own record of what
  is installed lists every locked package (`vendor/composer/installed.json`,
  `node_modules/.package-lock.json`...): an identical lockfile can sit over an
  incomplete install. Each step that reads it checks both. A map without that
  line (an older map) leaves the search to the step, by the same rules, and
  the step records what it used.
- **Passive** (default): what a visitor's browser does. Request pages, what
  they link to, and URLs the auditor provided; read headers, cookies, TLS. No
  login attempts, crafted payloads or scanning; every URL and identifier comes
  from a link or the auditor.
- In either regime, signing in with an account the auditor provides for the
  audit is a visitor's ordinary use, not a login attempt; its credentials are
  handled like a secret. Under passive, a form is submitted only to show its
  validation, with input it rejects. Under active, a step may also create
  data through the product's own forms with the auditor's test accounts (a
  registration, a character), each creation listed under `## Created on
  target` in the step's file; it never deletes anything, and resetting the
  data is the owner's.
- Parallel steps share the target: each uses its own browser context, never
  a profile another step signs in with, and remembers that another step's
  data may appear.
- On a target the auditor runs, a container may be inspected read-only
  (`docker exec` to read configuration and files, `docker ps`, `docker
  inspect`, `docker logs` filtered to the step's own requests): environment
  variables by name only, never their values. A command that prints
  configuration with values resolved (`docker inspect`, `docker compose
  config`) runs through a filter that drops them before anything is kept.
  Running the runtime itself to read its settings (`php -r 'ini_get(…)'`) is
  inspection; a project command (`bin/console`, `manage.py`) runs project
  code and is not. A store's content is read only through the product, as a
  visitor would.
- The target is its code and its runtime: each step that observes it checks
  which commit the code comes from and which image runs it, and that the
  image was built from the audited commit's build files; a difference is
  stated like a commit difference. An image the auditor built for the
  target may be scanned, as evidence of that build.
- Images are pulled by digest, or scanned from their registry without a
  pull. A tag a running container uses is never pulled or moved, and no
  local image is retagged.
- **Cloud read**, with `cloud_read: yes` or within the scope the engagement
  records (forge settings read with the auditor's own login count): it binds
  every step alike, and covers only the read-only access the owner gives for
  the audit, its credentials handled like a secret and kept outside the
  workspace; configuration is read through the provider's API, never
  changed, and the content of stores (objects, rows, secret values) is never
  read. Output is masked of secrets and personal data before it is kept.
- **The issue tracker** may be read (visibility, labels, a search for a
  fix's ticket, the default branch's commits and the issues closed since
  the audit) with the auditor's own access. Only `tickets` writes there:
  new issues, one per fix, with the permission the engagement records and
  the auditor's yes for the batch, and the dependency links the
  tracker's conventions use, made right after the waiting ticket and
  listed in the index that yes answered. Nothing else in it is edited, commented, closed or deleted,
  and no label or milestone is created.
- Passive also covers one TLS handshake per host, to read the protocol and
  the certificate. Enumerating protocols, ciphers or ports is scanning:
  active only, on the listed hosts.
- Development builds inject tools (debug toolbars, profilers, `/_profiler`,
  `/_wdt`): they are excluded from crawls, scans and measurements, and read
  only as the auditor's instruments. A development `robots.txt` that blocks
  everything is configuration to report on, not a rule for the audit's own
  crawl.
- Following links across the in-scope hosts (a crawl) is sequential, at most
  one request per second, with a page cap recorded in the output.
- No load or stress test (traffic meant to strain the target), in any regime:
  it degrades the target. A question that needs one is a lead for the owner.
- **Active**: with `testing: active`, on the listed `hosts`, inside `in_scope`.
  Stop at the first proof; read or keep no data that is not the auditor's. A
  step that could leave scope, touch such data, or change or degrade the target
  beyond the listed creations above becomes a lead for the owner to test.
- A secret is recorded by location, kind and presence in history. In every
  workspace file (map, findings, notes, reports) its value, default and
  placeholder values included, is written `<redacted>`, never quoted in full
  or in part. A secret is never used or tested for validity. Files known to
  hold secrets (`.env*`, fixtures with passwords) are read through a filter
  that masks values, and a tool that copies credentials into its report
  (session cookies, extra headers) has them removed before the report is
  kept.
- Personal data of real people, seen in the repository, on the target or in
  the owner's documents, is recorded by field and location and never copied
  into a workspace file; data the project's fixtures invent is not personal
  data.
- Credentials (an account the auditor provides, a fixture password) are read
  by the script that uses them and never printed: no command shows their
  value to the agent, in its output or its context.
- Parallel active steps each create their data with an account or object no
  other step uses, where the product allows one per account.
- Each tool run (scanners, analysers, audit commands, the `git log` commands
  and scripts an axis relies on) is scripted in
  `tool-output/<step>/run-<name>.sh` (`<step>`: `recon`, the axis, `verify`,
  `plan`, `report`, `tickets`; a later run of the same step in `tool-output/<step>/<run>/`,
  `<run>` being `lead-pass-<YYYY-MM-DD>` or `round-2` for an axis, the
  run's date `<YYYY-MM-DD>` for the others, `<YYYY-MM-DD>-2`, `-3`… for a
  second run the same day), raw output kept beside it, paths
  relative to the workspace so a copy reruns in place, times in UTC, auditor
  artifacts (`.gitnexus/`, caches, the workspace) excluded; in a container,
  the working copy is mounted read-only. Rules or scripts written for the run are kept there too;
  tool installs and caches (`node_modules`, vulnerability databases) go in
  `<workspace>/cache/`, which no deliverable cites. A run that read nothing
  (a ruleset that does not exist, an empty target list) is not a clean
  result: check what each run read.
- A count or a list cited as evidence comes from such a script, run with
  `bash`, never from an interactive shell: a shell hook can filter or
  truncate output without saying so.
- Each step lists its own skill version and the tools it ran,
  `name@version`, in its own output (the map's header, an axis's coverage, a
  verification note, the plan's header, the report's provenance); only
  `audit-kickoff` copies
  them into the engagement file, before the report. Steps may run in
  parallel, so none other writes the engagement file.
