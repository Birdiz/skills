# The run directory

One run is one directory, written by `scripts/run.py` and checked by
`scripts/validate.py`:

```
$XDG_STATE_HOME/birdiz-review/runs/<repo>/<branch>/<head short sha>/
├── run.json                  the run header
├── signals/<detector>.json   one output per detector (git-changes, migrations, config,
│                             routes, api-contracts, dependencies, assertions, public-api,
│                             fan-in, structure; import-graph-<stack> from a stack adapter:
│                             import-graph-php, import-graph-typescript, import-graph-python)
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
{"name": "squawk", "command": "squawk", "found": true, "version": "1.4.2",
 "needs": "nothing", "installs": false, "allowed": true}
```

A tool with an adapter also records what it needs to run on the trees the
run writes: `needs` (`nothing`, `dependencies` or `build`), `installs`
(whether it installs them itself), `allowed`, and `why` when it is not. A
tool needing a build is never used in this version; one needing
dependencies runs only on what is already installed; one that installs
them is never used, since an install runs the project's scripts and waits
for `execution` (ADR 0004). `roave-backward-compatibility-check` runs
`composer install` in its own clones of the repository, with no option to
skip it, so it is never run. `api-extractor` reads the `.d.ts` files a
TypeScript build writes, so it is never run either. `deptrac`,
`graphql-inspector`, `dependency-cruiser`, `griffe` and `import-linter`
install nothing and run; `dependency-cruiser` needs dependencies: it reads
TypeScript through the TypeScript compiler installed beside it, and skips
TypeScript files without one. `griffe check` compares two git references
by checking each out with `git worktree add` in the repository it is
pointed at, so it runs in a scratch repository the run writes from the two
trees, never in the reviewed one. `import-linter` puts the directory it
runs in first on `sys.path`, so it runs in a scratch directory holding
only its config and the root packages, `PYTHONPATH` unset. A tool is found
on `PATH` only, never looked up in the project's `node_modules/.bin` or
`.venv/bin` (an activated virtual environment is on `PATH`, by the
reviewer's choice).

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
  `contract-changed`, `required-added`. GraphQL: with `graphql-inspector`
  on the machine, `graphql-inspector diff` on the base and head schema
  files, its breaking and dangerous changes
  (`graphql-inspector:breaking`, `graphql-inspector:dangerous`, with no
  line: it prints none); without it, or when it fails (a schema split
  across files does not load alone), a gap, and the heuristic:
  `field-removed`, `field-changed`. A deleted contract: `contract-removed`.
  `tool` names each tool used, comma-separated, and `heuristic` is true
  when a file was read by the heuristic.
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

The PHP adapter's content detectors apply to changed `.php` files, test
files and templates (`*.blade.php`, ...) left out. A file without a
`<?php` tag, or one whose comments, strings or braces never close, is
`not_covered` (`not readable as PHP at the head: ...`), which makes it
`unproven`. A tool needing the whole base tree gets it written from git
objects into a temporary directory of the run directory, removed after the
detectors ran; nothing is checked out in the repository.

- `public-api`: the signature-level diff of each file's public API between
  the base and the head, labelled heuristic (`languages`: the languages of
  the files it applies to, `php`, `typescript`, `javascript`, `python`).
  Public means public, or protected in a class that is not final; a class
  or member marked `@internal` is left out. `class-removed` (naming the
  class that appears in its place, a rename), `class-changed` (became
  final, abstract or another kind; no longer extends or implements a
  type), `method-removed` (naming the method in its place), `function-removed`,
  `signature-changed` (a parameter removed, renamed, retyped, made
  required, a new required one, the return type, static or final),
  `visibility-reduced`, `interface-method-added`, `abstract-method-added`,
  `constant-removed` (enum cases included), `property-removed`,
  `property-changed`. Types are compared fully qualified, so importing a
  class under an alias is no change. Roave's BC check is never run (see the
  run header's tools), and a gap says so.
- `import-graph-php`: the PHP import graph, written in the stack-neutral
  format below ("An import graph comes from a stack adapter"), from which
  `structure.py` computes its new edges and cycles (`import-edge-added`,
  `import-cycle-added`). Written only when the diff has a PHP file or the
  head a `composer.json`. A module is the namespace segment under a PSR-4
  prefix of the head's `composer.json` (`App\Billing` under `App\`; a
  class right under the prefix belongs to the prefix's module), else the
  first two segments of a namespace the repository declares; `modules`
  says which rule held. An edge is a `use` of a class from a file of one
  module to the file of another that declares it, or whose name and
  namespace it has (PSR-4); a class of no file in the repository has none.
  The changed files are parsed at both sides; every other PHP file of the
  head tree is read up to its first declaration and stands for both sides.
  With a deptrac config at the head (`deptrac.yaml`, `deptrac.yml`,
  `depfile.yaml`, `depfile.yml`) and deptrac on the machine, `deptrac
  analyse` runs on the head tree and, when it has the config, the base
  tree, cache off, and each violation the base does not have is a
  `layer-violation` on its changed file. A PHP config, or YAML with
  `services:` or `imports:`, can load the project's code: deptrac is not
  run on it, and a gap says so. The output also holds `layers` (`config`,
  `checked`, `violations`, `new`) and `scanned`. Its signals feed the
  structure step: they are not rows of the contracts worksheet.

The TypeScript adapter's content detectors apply to changed `.ts`, `.tsx`,
`.mts`, `.cts`, `.js`, `.jsx`, `.mjs` and `.cjs` files, test files and
minified files (`*.min.js`) left out; `.vue` and `.svelte` files are read
by none. Its lexer blanks comments, strings, template literals, regular
expressions and JSX (`<` opens JSX in an expression everywhere but `.ts`,
where it is a type assertion). A file it can't finish is `not_covered`
(`not readable as TypeScript at the head: ...`), and so is a file with a
line over 5000 characters, or 500 on average (`minified or bundled at the
head ...`): both are `unproven`.

- `public-api`, for these files: the signature-level diff of each file's
  exports, labelled heuristic. Exports are `export` declarations, `export
  { a as b }`, `export default`, and the re-exports `export { a } from`
  and `export * from`. A file that exports only through CommonJS
  (`module.exports`, `exports.x`) is `not_covered`: its API is not read in
  this version. Private and `#` members are not API, protected ones are;
  a declaration or member marked `@internal` is left out. Types are
  compared as written, spaces aside: `string | number` and `number |
  string` differ, and adding an annotation is a change. A parameter
  renamed is none (TypeScript has no named arguments). `export-removed`
  (naming the export that appears in its place, a rename; a deleted file
  gets one, listing its exports), `export-changed` (a function became a
  class, a type, a value...), `signature-changed` (a parameter removed,
  retyped or made required, a new required one, a rest parameter, the
  return type, type parameters, an overload removed; for functions,
  methods and constructors), `class-changed` (became abstract, no longer
  extends or implements a type), `method-removed`, `property-removed`,
  `property-changed` (type, readonly, static, a method became a property),
  `visibility-reduced`, `abstract-member-added`, `member-removed`,
  `member-changed` and `interface-member-added` (a required member, for
  interfaces), `type-changed` (a type alias or an annotated variable),
  `enum-member-removed`, `enum-member-changed` (its value, implicit
  numbers counted), `reexport-removed` (`export * from`). API Extractor is
  never run, and a gap says so.
- `import-graph-typescript`: the import graph, in the same stack-neutral
  format, from `import`, `export ... from`, `import x = require()`,
  `require()` and `import()` with a string, type-only imports included.
  Written only when the diff has such a file: a `package.json` beside code
  of another stack does not make the Import graph area evaluated. A
  specifier resolves to a file of the repository
  through a relative path (an ESM `./x.js` names `./x.ts`, a directory its
  `index`), the `paths` and `baseUrl` of the nearest `tsconfig.json` or
  `jsconfig.json` (relative `extends` followed), or a workspace package's
  name (a directory with a `package.json` and a `name`), its `exports`,
  `types`, `module` or `main` mapped from `dist/` to `src/` when the build
  output is not in the tree, else `src/index`. A package outside the
  repository has no edge. A module is the first directory under a source
  root (`src/`, `lib/`, `app/`, `source/`) of a package, else the
  package's first directory; a file right under a source root, or a
  package, belongs to it, and `/` is the root; `modules` says which
  packages and aliases it found. With `dependency-cruiser` on the
  machine, `depcruise --no-config --ts-pre-compilation-deps --output-type
  json` runs on the head tree and the base tree (`--ts-config` when the
  tree has a `tsconfig.json`), and its resolved dependencies are the edges
  (`line` taken from the parser where it resolved the same pair, else
  `null`), when it read every changed file at both sides; otherwise a gap
  says why (not found, it failed, it skipped a file: no TypeScript
  compiler beside it) and the parser's resolution stands. The output also
  holds `languages` and `scanned`. Its signals feed the structure step.

The Python adapter's content detectors apply to changed `.py` files, test
files left out (`.pyi` stubs are read by none). Each file is parsed with
the standard `ast` module of the interpreter that runs the review; a file
it can't parse (syntax newer than that interpreter, Python 2) is
`not_covered` (`not readable as Python by Python 3.<n> at the head: ...`),
so `unproven`. No project code is imported or run.

- `public-api`, for these files: the signature-level diff of each
  module's public names, labelled heuristic. Public means listed in a
  static `__all__` (a list or tuple of strings, `+=`, `.append`,
  `.extend`), else not starting with `_`; a module under a `_private`
  part of its path exports only its `__all__`; an import is API only when
  `__all__` lists it, it is written `import x as x`, or it is a relative
  import of an `__init__.py`. A class member is public unless it starts
  with a single `_` (dunders are public: `__init__` is the constructor).
  Python passes arguments by keyword, so a renamed parameter is a change,
  except a positional-only one; one taken by `**kwargs` or `*args` after
  the change is not. A type is compared as written, and only when both
  sides have one: an annotation added or removed is no change.
  `function-removed`, `class-removed`, `name-removed` (a variable, a type
  alias or a re-export; also a name dropped from `__all__`), all naming
  what appears in their place (a rename; a deleted file gets one signal
  listing its names), `name-changed` (a function became a class, a value's
  type), `signature-changed` (a parameter removed, renamed, moved, made
  keyword-only or positional-only, made required, its default or type
  changed, a new required one, `*args` or `**kwargs` removed, the return
  type, became or stopped being async, an overload removed; for functions,
  methods and constructors, a dataclass's or a `NamedTuple`'s generated
  one included), `class-changed` (no longer inherits a class, became
  `@final`), `method-removed`, `property-removed` (an attribute, a
  property, or `self.x` set in `__init__`), `property-changed` (its type,
  a property that lost its setter, a method that became a property),
  `abstract-method-added`, `protocol-member-added` (a member added to a
  `Protocol`), `type-changed` (a `type` alias), `enum-member-removed`,
  `enum-member-changed` (its value, `auto()` numbered as Python 3.13
  does). With `griffe` on
  the machine, each package the diff touches that exists at both sides
  goes through `griffe check --no-inspection --format github` between a
  `review-base` and a `review-head` commit of that package, in a scratch
  repository written from the two trees under the run directory (hooks
  off); its breakages are the package's signals (`griffe:object-removed`,
  `griffe:parameter-removed`, `griffe:parameter-moved`,
  `griffe:parameter-kind-changed`, `griffe:parameter-default-changed`,
  `griffe:parameter-required`, `griffe:parameter-added-required`,
  `griffe:return-type-changed`, `griffe:object-kind-changed`,
  `griffe:attribute-type-changed`, `griffe:base-removed`,
  `griffe:attribute-value-changed`), `tool` names it, and a breakage in a
  file the diff does not change (a re-export) is counted in a gap. A file
  outside such a package, a package griffe fails on, or griffe missing:
  the heuristic, and a gap.
- `import-graph-python`: the import graph, in the same stack-neutral
  format, from every `import` and `from ... import` statement, in a
  function or under `if TYPE_CHECKING:` too. Written only when the diff has
  a Python file. A file in a package (a directory with `__init__.py`) is
  named from the directory above its topmost package, or from the closest
  root above a namespace package (`src/acme/billing/` with no
  `src/acme/__init__.py` is `acme.billing`); any other from the closest
  root above it (the repository root, a directory with
  `pyproject.toml`, `setup.py` or `setup.cfg`, or its `src/`), and a
  script also imports the modules beside it. An import maps to the file it
  loads: the deepest module of `import a.b.c`, the submodule a `from`
  import names, else the module it imports from; of two copies of a
  package, the one under the importer's root, else the nearest package
  (never a loose module of another root, nor a name of the standard
  library); a relative import above the top-level package has none. An
  import of no file in the repository (the standard library, a dependency) has
  no edge. A module is a root's top-level package, or its first
  subpackage when the root has one top-level package (`tests`, `docs`,
  `scripts` and the like aside), named by its dotted path (`shop.billing`),
  after `<root>:` outside the repository root and `src/`; a file outside
  any package belongs to its directory (`/` for the root). With an
  import-linter config at the head (`.importlinter`, or `setup.cfg` with
  `[importlinter]`, or `pyproject.toml` with `[tool.importlinter]`) and
  import-linter on the machine, `lint-imports --config <file> --no-cache`
  runs on the head tree and, when it has the config, the base tree, each
  time in a scratch directory holding only the config and the root
  packages copied from that tree, `PYTHONPATH` unset (it puts the
  directory it runs in first on `sys.path`, so no other file of the
  project can stand in for a module it loads); each
  import of a broken contract the base does not have is a
  `contract-broken` signal on its changed file. A config with
  `contract_types`, or a dotted root package, imports the project's code,
  and a root package named like a standard library module would shadow
  it: import-linter is not run on it, and a gap says so. The output also holds
  `contracts` (`config`, `checked`, `kept`, `broken`, `results` per
  contract, `broken_at_base`, `new`), `languages` and `scanned`. Its
  signals feed the structure step.

`fan-in` is not a content detector. It lists the public symbols the diff
removes or changes in code files, test files left out (`symbols`: `path`,
`symbol`, `change` `removed`, `signature` or `body`, `line`, `fan_in`, the
references outside the diff, and the first `refs` as `path:line`), and
`scanned`, the files searched. The count is a search over the head tree,
comment lines skipped, labelled heuristic: a name of three letters or
fewer, or a common one, is `unknown`. A TypeScript or JavaScript symbol
comes from the TypeScript parser: an export's name, `Class.member` or
`Interface.member`, `Class.constructor`, a `body` change being an exported
function or a public method the base already had whose lines a hunk
touches. Its references are searched in TypeScript and JavaScript files,
lexed first so a word in a string or a comment is none (a JSX tag name, and
the code inside JSX, are references): an export as a
word that is not a property (`total`, not `.total`), a member as `.member`
or `?.member` whatever the receiver, a constructor as `new Class(` or
`extends Class`. A Python symbol comes from the Python parser: a public
name, `Class.member`, `Class.__init__`, a `body` change being a function or
a public method or property the base already had whose lines a hunk
touches. Its references are searched in Python files with strings and
comments blanked (the code inside an f-string's fields is kept): a name
as a word or through its module's name (`total`, `invoice.total`), not as
another object's attribute, a member as `.member`, a constructor as
`Class(` or a class inheriting it. A PHP symbol comes from the PHP
parser: `Class::method`, `Class::CONST`, `Class::$property`, or a class or
function name, a `body` change being a public method the base already had
whose lines a hunk touches. Its references are searched in PHP files by how
it is used (`->method(`, `::method(`, `::CONST`, `new Class(` for a
constructor, the class name as a word), whatever the receiver. Other symbols are searched as a word in every code file. A
removed symbol or a changed signature with references outside the diff is
a signal (`symbol-removed`, `symbol-signature`), except for PHP,
TypeScript, JavaScript and Python, whose break is the `public-api` signal.

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

- **Signals**: one row per signal of every detector but `git-changes` and
  the import graphs (`import-graph-<stack>`),
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
