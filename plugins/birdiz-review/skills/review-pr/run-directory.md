# The run directory

One run is one directory, written by `scripts/run.py` and checked by
`scripts/validate.py`:

```
$XDG_STATE_HOME/birdiz-review/runs/<repo>/<branch>/<head short sha>/
├── run.json                  the run header
├── signals/<detector>.json   one output per detector (git-changes, migrations, config,
│                             routes, api-contracts, dependencies, assertions, fan-in,
│                             structure; import-graph-<stack> from a stack adapter)
├── findings/<axis>.md        intent.md, contracts.md, structure.md
├── brief.md                  the brief, a projection of the files above
├── sources.json              the spec, tickets and PR body read, and their contract status
├── sources/                  a copy of each artifact read
├── diff.patch                the unified diff from the merge base to the head
└── repo-<head short sha>/    the head tree, written from git objects
```

`XDG_STATE_HOME` defaults to `~/.local/state`. `<repo>` is the origin
remote's `owner/name`, else the main working tree's name; `<branch>` is the
head's branch (a remote branch without its remote; a PR's head branch),
else the head as given.
Both are escaped into one path component (`feature/x` is `feature%2Fx`). The
short sha has 12 characters. The root is fixed, not a setting, and never
inside the reviewed repository.

## Run header

`run.json`: `schema` (`review-pr@<version>`), `core`
(`finding-core@<version>`), `repo`, `branch`, `target` (as resolved,
`base..head`), `base` and `head` (`{ref, sha}`), `merge_base`, `diff`
(`<merge base short sha>..<head short sha>`: the diff always runs from the
merge base), `started`, `tools`, `detectors` (the outputs under
`signals/`), `sources` (`sources.json`), `patch` (`diff.patch`, renames
detected, what the judgment steps read), and for a pull request `pr`
(`number`, `url`, `title`, `state`, `base` and `head` branch names,
`fetched`: the refs whose objects had to be fetched from origin). `tools` lists every detector tool looked for on this machine,
found or not, with the version of each one found:

```json
{"name": "squawk", "command": "squawk", "found": true, "version": "1.4.2"}
```

Tools are detected on every run and stored nowhere else: they depend on the
machine, not the repository.

`risk_map` is the repository's `docs/agents/review.md`, written by
`review-setup`, as committed at the base (read from git objects, so a
branch can't narrow its own): `path`, `sha` (the base's), `found`,
`stacks`, `rows` (`{glob, zone}`, gitignore-like globs) and `problems`
(`{line, message}`, rows left out). A header without it is a run that did
not read one.

## Sources

`sources.json` records what the change was supposed to do, found and read
as [pocock-contract.md](pocock-contract.md) says: `contract` (the upstream
commit it was checked against), `found_by` (the rule that found the spec
or tickets, `null` when none did), `tracker` (the tracker doc at the base:
`status`, `kind`, `detail`), `pr` (the PR body: `status` `declared`, `not
declared` or `drift`, `door`, `blast_radius`, `drift`), `spec` (its ref),
`artifacts`, `dimensions` and `ask` (the question for the user when nothing
was found).

Each artifact: `ref` (`#N` or a path in the head tree), `role` (`spec`,
`ticket` or `unknown`), `scope` (`spec`, `in scope` or `sibling`),
`found_by`, `status` (`ok`, `drift` or `unreadable`), `drift` (what the
contract expected and did not find), `file` (its copy under `sources/`),
and what was parsed: a ticket's `template` (`issue` or `local`),
`criteria` (`{text, checked, line}`), `parent`, `blocked_by` and
`relations` (native `parent` and `sub_issues` when the forge gave them); a
spec's `sections` and `tickets_by`.

`dimensions.intent` is `evaluable` or `not-evaluable (<why>)`: no spec
found, the user said there is none, the tracker can't be read, or
`contract drift: <role> <ref>, <what>` for a spec or in-scope ticket that
drifted. A sibling ticket's drift is reported and does not count.
`dimensions.declared` is `declared`, `not declared`, `no PR body read` or
`not-evaluable (contract drift: ...)`.

## Detector outputs

Each detector writes one JSON file with its own coverage: `detector`,
`version`, `content` (whether it reads what a file's content means),
`applies_to` (file patterns), `tool` (`<name>@<version>`, or none for a
heuristic), `heuristic`, `covered` (the files it could judge),
`not_covered` (`{path, reason}`), `gaps` (a tool missing or failed, said
in the brief's coverage gaps), `signals` (`{path, kind, reason}`, a `line`
in the head when it has one, an `excerpt` of the code).

`git-changes` is not a content detector: it lists every changed file
(`files`: `path`, `change`, `from` for a rename or a copy, and `hunks`, the
`[start, count]` line ranges of its hunks in the head, empty for a deleted
file, a rename with no change or a binary file), the new directories, and
signals each file added, deleted, renamed, copied or changed in type. A
modified file gets no signal from it.

The stack-agnostic content detectors, run on every run. Each applies to
the changed files its classifier accepts: `applies_to` lists them, escaped
so that each pattern matches its own path only. A file it can't read
(binary, not UTF-8, not valid JSON for a manifest) is `not_covered` with
the reason, which makes the file `unproven`. Nothing runs the reviewed
project: the head is the tree written from git objects, the base side is
read from the merge base's objects.

- `migrations`: migration files by framework convention (raw SQL under a
  `migrations/`, `migrate/` or `db/migration/` directory or named
  `*.up.sql`, Prisma, Laravel, Doctrine, Alembic, Django, Rails). Signals
  on added lines: `drop`, `rename`, `type-change`, `not-null` (with an
  added `NOT NULL` column without a default), `data-rewrite`; on an added
  migration with no way back, `no-down`; `migration-edited`,
  `migration-deleted`; `schema-changed` for a Prisma schema. A framework
  migration always gets `framework-migration`: its SQL is not generated in
  this version, so the contracts step reads it as code. Raw SQL also goes
  through `squawk` when it is on the machine (`squawk:<rule>`); without
  it, a gap says the heuristic read it alone.
- `config`: environment templates (`.env*`, `*.env.example`, ...) and
  configuration files (`config/`, `settings.py`, `application*.yml`,
  `appsettings*.json`, compose files). `env-added` (with no default value
  when empty), `env-removed`, `env-default-changed`, `config-changed`,
  `config-added` (lines added to an existing file), `config-deleted`, and
  `env-required`: a variable an added line reads
  with no default, mentioned nowhere at the base. `env-required` is also
  raised on any changed code file, which the detector scans without
  covering it.
- `routes`: route files by convention (`routes/`, `config/routes*`,
  `urls.py`, `routes.*`, `*.routes.ts`) and file-based routes
  (`app/**/route.ts`, `pages/api/**`). `route-removed`, `route-changed`,
  `route-added` (new surface, so a route file that gains a route is never
  `skim`), `route-file-deleted`, `route-file-renamed`; route decorators and
  attributes removed from any changed code file, scanned without covering
  it.
- `api-contracts`: OpenAPI files by name or by an `openapi:` or
  `swagger:` key, and GraphQL schemas. With `oasdiff` on the machine,
  `oasdiff breaking` on the base and head (`oasdiff:<id>`); without it, a
  gap, and the heuristic: `path-removed`, `operation-removed`,
  `contract-changed`, `required-added`. GraphQL: `field-removed`,
  `field-changed`. A deleted contract: `contract-removed`.
- `dependencies`: manifests (`package.json`, `composer.json`,
  `pyproject.toml`, `requirements*.txt`, `Pipfile`, `Gemfile`, `go.mod`,
  `Cargo.toml`) and their lockfiles. `dependency-added`,
  `dependency-removed`, `dependency-changed` (saying when the major
  version moved), `runtime-changed` (engines, `php`, `requires-python`,
  `go`, ...), `manifest-deleted`, `manifest-changed` (changed outside its
  dependencies: scripts, entry points), and `lockfile-changed`, with or
  without its manifest.
- `assertions`: test files by convention (`tests/`, `test_*.py`,
  `*.test.ts`, `*Test.php`, `*_spec.rb`, ...). Per edit, between context
  lines: `assertion-modified`, `assertion-removed`; `skip-added`,
  `focus-added`; `test-code-changed` once per file for existing test lines
  changed outside assertions; `test-deleted`. A test file that only gains
  lines gets no signal, so it can be `skim`.

`fan-in` is not a content detector. It lists the public symbols the diff
removes or changes in code files, test files left out (`symbols`: `path`,
`symbol`, `change` `removed`, `signature` or `body`, `line`, `fan_in`, the
references outside the diff, and the first `refs` as `path:line`), and
`scanned`, the files searched. The count is a word search over the head
tree, comment lines skipped, labelled heuristic: a name of three letters or
fewer, or a common one, is `unknown`. A removed symbol or a changed
signature with references outside the diff is a signal
(`symbol-removed`, `symbol-signature`).

`structure` is not a content detector and has no signals: a new file
already has its `git-changes` signal. It records what the structure step
reads:

- `new_files`: each file added, copied or renamed (`path`, `change`,
  `from`), its `class` by path convention, `why`, its `module` and
  `new_module`. Classes, first match wins: `test`, `migration`, `config`
  (environment, configuration, manifest, lockfile, CI or build file),
  `entry point` (a route file, `main`, a CLI, a controller, a command, a
  handler), then for code `module` (its module is new), `layer` (a new
  directory whose name no directory at the merge base has, such as a first
  `projections/`) or `source`, and `other` for the rest. A module is the
  first directory under `src/`, `lib/`, `app/`, `packages/`, `plugins/` and
  the like, else the top-level directory. `new_modules` lists the new ones.
- `dependencies`: each dependency a changed manifest adds, `D<n>`
  (`path`, `name`, `spec`, `line`), its `category` when it is a known
  library (`http-client`, `validation`, `state`, `logging`, `orm`, `date`,
  `test framework`) and `peers`, the manifest's dependencies of the same
  category at the base.
- `domain`: the domain doc as committed at the base (`doc`: `ok`, `drift`,
  or `missing`, when Pocock's defaults are read: `GLOSSARY.md` or
  `GLOSSARY-MAP.md` at the root, `docs/adr/`); the glossary at the head
  (`glossary`: `ok`, `absent`, `drift`, its `files` with their `terms`, and
  `map` for a `GLOSSARY-MAP.md`); the ADRs at the head (`adrs`: `ok`,
  `absent`, `drift`, the `dirs` with their files, the ones the diff
  `changed`). A domain doc template such as `src/<context>/docs/adr/`, and
  `<context>/docs/adr/` beside each glossary of the map, are expanded
  against the head tree.
- `terms`: the type names the diff defines in code, tests left out, that
  no glossary term names and that are new to the repository (neither the
  name nor its domain part, `Order` of `OrderController`, is at the merge
  base), `T<n>` with a `note` when the glossary says to avoid the word;
  `known_terms`, the ones a term names. Technical words at either end
  (`Repository`, `Controller`, `Abstract`) are left out of the comparison.
- `import_graphs`: the import graph outputs of the run.
- `areas`: the structure coverage areas the run fixes: `Import graph`
  `not-evaluable (no stack adapter supplies an import graph)` without one,
  `Glossary` `not-evaluable (no glossary)` and `ADRs` `not-evaluable (no
  ADRs)` when none exists at the head (absent is not drift), and
  `not-evaluable (contract drift: <what>)` for a domain doc that names no
  glossary or no ADR directory, a glossary map that links no glossary, or
  a glossary with no `**Term**:` line.

An import graph comes from a stack adapter, as an output named
`import-graph-<stack>` with a `graph` in one stack-neutral format:

```json
{"base": {"modules": {"src/Billing/Invoice.php": "Billing"},
          "edges": [{"from": "src/Billing/Invoice.php", "to": "src/Ordering/Order.php", "line": 5}]},
 "head": {"modules": {}, "edges": []}}
```

Each side maps files to modules and lists the file-level imports, with the
line of the import in the importing file. `structure.py` computes, whatever
the stack, the `new_edges` (pairs of modules the head imports in that
direction and the base did not, with the file edges that make them) and
the `new_cycles` (modules that import each other at the head, not within a
cycle of the base), and signals the importing file of each
(`import-edge-added`, `import-cycle-added`). The contracts step leaves
these signals to the structure step.

## Review finding

The finding core (evidence, finding and lead, status, severity and
confidence, coverage, `sensitive`, `promptable`, ID shapes), with:

- axes `intent` (`INT`), `contracts` (`BRK`), `structure` (`STR`), one
  findings file each; IDs `F-INT-001`, `L-BRK-01`;
- keys `diff` (the run's), `attention` (`must-read | glance`),
  `blocks_merge` (`true | false`), `fan_in` (a count or `unknown`), and on a
  disagreement finding both `declared` and `detected`;
- prose sections **Evidence.** then **Reviewer question.**, the question
  the reviewer should ask themselves at that place.

````markdown
### F-BRK-001 Public method takes a new required argument

```yaml
id: F-BRK-001
axis: contracts
status: unverified
severity: high
confidence: high
sensitive: false
promptable: true
locations:
  - src/app.py:1
diff: 0123456789ab..ba9876543210
attention: must-read
blocks_merge: true
fan_in: 3
```

**Evidence.** `src/app.py:1` "def greet(name, punctuation):" adds a required
argument.

**Reviewer question.** Do the three callers outside the diff pass it?
````

`status` stays `unverified`: no verifier exists in this version, and the
reader of the brief is the verifier. `sensitive: true` keeps a finding out
of any projection meant to be posted publicly; the brief is local.

A step that did not run still writes its findings file, so that its
coverage says why: the reason its sources are not evaluable
(`no spec found`, `contract drift: ...`), or `step not run yet` for a
step whose worksheet waits for it.

## Intent findings file

`findings/intent.md` is written by `run.py` as a worksheet when the intent
sources are evaluable, and filled by the intent step
([steps/intent.md](steps/intent.md)). Between `## Coverage` and
`## Findings` it holds three tables, which only this file may have:

```markdown
## Criteria

| Criterion | Status | Hunks | Finding |
|---|---|---|---|
| #40 AC1 `sources/issue-40.md:7` "An unused link signs the customer in" | found | `src/auth/link.py:12-20`, `tests/test_link.py:4-15` | |
| #40 AC2 `sources/issue-40.md:8` "A used link is refused" | not found | | F-INT-001 |

## Files

| File | Justified by | Finding |
|---|---|---|
| `src/auth/link.py` | #40 AC1 | |
| `tests/test_link.py` | #40 AC1 | |
| `src/billing/invoice.py` | out of scope | F-INT-002 |

## Decisions

None.
```

- **Criteria**: one row per acceptance criterion of the in-scope tickets,
  `<ticket ref> AC<n>` in the order of `sources.json`. Status `found`,
  `partial` or `not found`. `found` and `partial` name hunks; `not found`
  names none. `partial` and `not found` cite a finding.
- **Files**: one row per changed file, justified by criteria (`#40 AC1`),
  in-scope tickets or the spec, or `out of scope` alone with a finding. A
  sibling ticket never justifies a file.
- **Decisions**: one row per change against an item of the spec's
  Implementation Decisions or Out of Scope: the item as a pointer into the
  spec's copy, inside one of those sections, the change, and a finding.
  `None.` when there is none.
- A hunk entry is `` `path:start-end` `` or `` `path:line` ``, meeting one
  of the file's hunks, or the path alone for a file with no line hunk.
- Every intent finding is cited by a row.

The worksheet has every row, with `?` where the step judges, and `Axis:
not-evaluable (step not run yet)`. The validator reports that as `PENDING
intent` (an error with `--require intent`). Once the axis is `evaluated` or
`partial`, it checks the rows against `sources.json`, the changed files and
their hunks: a criterion or a file missing, a row left `?`, a hunk no
change meets, a finding not cited or cited and absent are errors. An intent
file `evaluated` on sources that are not evaluable is an error too.

## Contracts findings file

`findings/contracts.md` is written by `run.py` as a worksheet on every run
and filled by the contracts step ([steps/contracts.md](steps/contracts.md)).
Between `## Coverage` and `## Findings` it holds two tables, which only
this file may have:

```markdown
## Signals

| Signal | Judgment | Finding |
|---|---|---|
| S1 `db/migrations/002_drop_email.sql:1` migrations `drop`: drops a table, a column or another object, or empties a table | one-way | F-BRK-001 |
| S2 `tests/test_app.py:6` assertions `assertion-modified`: 1 assertion line(s) changed | minor | |

## Declared

| Declared | Detected | Finding |
|---|---|---|
| PR #7: Door `two-way`, Blast Radius `local` | one-way | F-BRK-002 |
```

- **Signals**: one row per signal of every detector but `git-changes`,
  `S<n>` in the order of the header's `detectors`, naming the signal's
  file. Judgment `one-way` (reverting the merge does not undo it),
  `breaking` (a consumer outside the diff breaks, a revert undoes it) or
  `minor`. `one-way` and `breaking` cite a finding.
- **Declared**: one row. The PR's declared Door and Blast Radius, `not
  declared` or `not read`; the Door the step detected, `one-way` or
  `two-way`. `one-way` when a row is judged `one-way` (or the row cites the
  finding that says why), `two-way` otherwise. When the PR declares a Door
  that differs, the row cites the disagreement finding, whose `declared`
  and `detected` are the two Doors. With no Door declared, a disagreement
  finding is an error.
- A contracts finding no row cites is allowed: a break in the code no
  detector signalled.

The worksheet has every row, with `?` where the step judges, and `Axis:
not-evaluable (step not run yet)`: `PENDING contracts`, an error with
`--require contracts`. Once the axis is `evaluated` or `partial`, the
validator checks the rows against the detector outputs and `sources.json`.

## Structure findings file

`findings/structure.md` is written by `run.py` as a worksheet on every run
and filled by the structure step ([steps/structure.md](steps/structure.md)).
Between `## Coverage` and `## Findings` it holds three tables, which only
this file may have:

```markdown
## Dependencies

| Dependency | Needed | Why | Finding |
|---|---|---|---|
| D1 `package.json:4` `got` ^14.0.0 (dependencies), http-client, beside `axios` | not needed | axios already calls HTTP | F-STR-001 |

## Terms

| Term | Judgment | Finding |
|---|---|---|
| T1 `src/billing/batch.ts:1` `InvoiceBatch` | domain term | F-STR-002 |
| T2 `src/ordering/order.ts:2` `RetryPolicy` | not a domain term | |

## Imports

None.
```

- **Dependencies**: one row per `D<n>`. Needed `needed` or `not needed`,
  and **Why** says in a few words; `not needed` cites a finding.
- **Terms**: one row per `T<n>`, `domain term` (it cites the finding that
  says the glossary lacks it, or that it uses a word the glossary avoids)
  or `not a domain term`. `None.` when the glossary is not evaluable.
- **Imports**: one row per new edge then new cycle of each import graph
  output, `G<n>`, `fits` or `boundary`; `boundary` cites a finding.
  `None.` without an import graph.
- A structure finding no row cites is allowed: a new module or layer
  nothing asks for, a pattern divergence, a change against an ADR, a
  decision no ADR records.

The worksheet has every row, with `?` where the step judges, the areas the
run fixed already set, and `Axis: not-evaluable (step not run yet)`:
`PENDING structure`, an error with `--require structure`. Once the axis is
`evaluated` or `partial`, the validator checks the rows against the
detector outputs, and that a fixed area keeps its status while the others
are judged.

## Buckets

Every changed file lands in exactly one bucket, by these rules in order:

1. `must-read`: a finding with `attention: must-read` points at it;
2. `unproven`: no content detector applies to its file type, or one that
   applies did not cover it;
3. `glance`: a detector signalled on it, a finding points at it, or it is in
   a risk zone; the reason is shown;
4. `skim`: everything else, which means at least one content detector
   covered it, every applicable one did, none signalled on it, no finding
   points at it, and it is outside the risk map. Its proof names the
   detector outputs.

A judgment step moves a file up by raising a finding, never down to `skim`.
A file matching a glob of the risk map names its zone and glob, as in
"risk zone auth (`src/Security/**`)", in whichever bucket it lands; the
validator rejects it in `skim`.

## Brief

`brief.md`, regenerated by `scripts/brief.py` from the run header, the
detector outputs and the findings files, never edited by hand. Sections, in
order: Declared vs detected (the PR's Door and Blast Radius, or "Risk not
declared" when no PR body was read or it has no `Merge Danger`; then each
disagreement finding; then a table with the declared Door beside the
detected one and the Blast Radius beside the risk zones the changed files
touch and the most referenced changed public symbols), New structure (the
new modules, the new files by class, each new dependency with its category
and the step's judgment, the import graph, the glossary and the ADRs),
Must read (each file,
then each finding: `file:line`, reason, reviewer question; then the
`must-read` findings that point at no changed file, such as a criterion
not found), Glance (with the reason, then the `glance` findings that point
at no changed file), Skim (with the proof), Unproven, Coverage gaps (the dimensions not
run, the structure areas the run fixed as not evaluable, the tools found
and not found, what a detector did not cover, the spec and tickets found
and any contract drift), Verdict.

## Verdict

One line, then its reasons:

```
Proposed verdict: fix, round 1 (attention map only: gates, test integrity, adversarial not run).
```

- `close-and-reprompt`: intent misread, when the intent step ran on
  evaluable sources (more than half of the acceptance criteria `not found`,
  a file `out of scope`, or a change against a stated decision); or the
  third distinct head of the branch, or a later one, still has a
  `blocks_merge` finding (the stop rule);
- `fix`: at least one `blocks_merge` finding;
- `merge`: none.

When the intent step ran, a reason line counts its tables; when the
contracts step ran, another counts its judgments and gives the detected
Door; when the structure step ran, a third counts the new files and
modules, the dependencies not needed, the terms judged domain terms and
the imports across a boundary. A `blocks_merge` contracts finding with sound intent is a `fix`. When the intent
sources are not evaluable (no spec, the user said there is none, contract
drift), the parenthesis starts with it, as in `merge, round 1 (intent not
checked: no spec found; contracts, structure, gates, test integrity,
adversarial not run)`, and misread intent can't be proposed. The
parenthesis always says what did not run. The round is the number of distinct head shas among the run
directories of the same branch: running again on the same head is not a new
round. Findings are not matched across runs.
