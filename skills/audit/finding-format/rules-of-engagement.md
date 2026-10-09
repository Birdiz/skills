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
- **Active**: with `testing: active`, on the listed `hosts`, inside `in_scope`.
  Stop at the first proof; read or keep no data that is not the auditor's. A
  step that could leave scope, touch such data, or change or degrade the target
  becomes a lead for the owner to test.
- A secret is recorded by location, kind and presence in history. In every
  workspace file (map, findings, notes, reports) its value, default and
  placeholder values included, is written `<redacted>`, never quoted in full
  or in part. A secret is never used or tested for validity.
- Each tool run (scanners, analysers, audit commands, the `git log` commands
  and scripts an axis relies on) is scripted in
  `tool-output/<step>/run-<name>.sh` (`<step>`: `recon`, the axis, `verify`),
  raw output kept beside it, auditor artifacts (`.gitnexus/`, caches, the
  workspace) excluded; in a container, the working copy is mounted read-only.
  Rules or scripts written for the run are kept there too.
- A count or a list cited as evidence comes from such a script, run with
  `bash`, never from an interactive shell: a shell hook can filter or
  truncate output without saying so.
- Each step lists the tools it ran, `name@version`, in its own output (the
  map's header, an axis's coverage, a verification note); only
  `audit-kickoff`, at the end, copies them into the engagement file. Axes may
  run in parallel, so none writes the engagement file.
