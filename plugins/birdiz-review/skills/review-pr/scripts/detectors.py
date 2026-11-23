"""The stack-agnostic detectors the contracts step reads: what a change does
to the contracts that live outside the diff's consumers.

Each one reads the changed files of its type and writes one output under
`signals/`, with its own coverage:

- `migrations`: migration files by framework convention (raw SQL, Prisma,
  Laravel, Doctrine, Alembic, Django, Rails). Destructive statements,
  renames, `NOT NULL`, type changes, data rewrites, a missing down path, an
  edited or deleted migration. Raw SQL also goes through `squawk` when it is
  on the machine. Framework migrations always get a signal: their SQL is
  not generated (that means running the project), so the step reads them
  as code.
- `config`: environment templates and configuration files. Variables added,
  removed or with a new default, configuration lines removed or changed,
  and environment variables read with no default that the base never
  mentions, in any changed file.
- `routes`: route files by convention. Route lines removed or changed, a
  file-based route deleted, and route decorators or attributes removed from
  any changed file.
- `api-contracts`: OpenAPI and GraphQL files. With `oasdiff` on the machine,
  its breaking changes; otherwise the paths and operations removed and the
  contract lines changed. GraphQL types and fields removed or changed.
- `dependencies`: dependency manifests and lockfiles. Dependencies added,
  removed or changed, the runtime constraint changed, a lockfile changed
  with or without its manifest.
- `assertions`: test files. Assertions changed or removed, skip and focus
  markers added, existing test code changed, a test file deleted.
- `fan-in`: not a content detector. The public symbols the diff removes or
  changes in code files, and the references to each outside the diff, a
  word search labelled heuristic.

A content detector applies to the changed files its classifier accepts
(`applies_to` lists them, escaped), covers the ones it could read, and says
why it could not read the others. Nothing here runs the reviewed project:
tools read the files the run wrote from git objects.
"""
import codecs
import json
import os
import re
import shutil
import subprocess

CODE_EXT = re.compile(r"\.(py|js|jsx|ts|tsx|mjs|cjs|php|rb|go|java|kt|kts|cs|rs|swift|scala|ex|exs)$")
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", "__pycache__", ".venv", "venv",
             "coverage", ".next", ".nuxt", ".tox", ".mypy_cache", ".pytest_cache"}
MAX_BYTES = 1 << 20
EXCERPT = 100
TOOL_TIMEOUT = 120


def excerpt(text):
    text = " ".join(str(text).split())
    return text if len(text) <= EXCERPT else text[:EXCERPT - 1] + "…"


def escape(path):
    """A path as an fnmatch pattern that matches only itself."""
    return re.sub(r"([*?\[])", r"[\1]", path)


def comment(text):
    s = text.strip()
    return not s or s.startswith(("#", "//", "/*", "*", "--", "<!--", ";"))


# --- The patch ----------------------------------------------------------------

def patch_path(text, side):
    """The path of a `--- a/x` / `+++ b/x` header line, None for /dev/null."""
    text = text.rstrip("\n").split("\t", 1)[0]
    if text == "/dev/null":
        return None
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = codecs.escape_decode(text[1:-1].encode("utf-8"))[0].decode("utf-8", "replace")
    return text[2:] if text.startswith(side + "/") else text


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_patch(patch_bytes):
    """{path: [hunk]}: each hunk a list of (op, text, old line, new line),
    op `+`, `-` or ` `. A removed line's new line is where the removal sits
    in the head. Keyed by the new path, the old one for a deleted file."""
    out, path, old, in_header, hunk = {}, None, None, False, None
    old_no = new_no = 0
    for raw in patch_bytes.decode("utf-8", "replace").split("\n"):
        if raw.startswith("diff --git "):
            path, old, in_header, hunk = None, None, True, None
        elif in_header and raw.startswith("--- "):
            old = patch_path(raw[4:], "a")
        elif in_header and raw.startswith("+++ "):
            path = patch_path(raw[4:], "b") or old
            out.setdefault(path, [])
        elif raw.startswith("@@") and path is not None:
            in_header = False
            m = HUNK.match(raw)
            if m:
                old_no, new_no = int(m.group(1)), int(m.group(3))
                hunk = []
                out[path].append(hunk)
        elif hunk is not None and raw[:1] in ("+", "-", " "):
            op = raw[0]
            if op == "+":
                hunk.append(("+", raw[1:], None, new_no))
                new_no += 1
            elif op == "-":
                hunk.append(("-", raw[1:], old_no, new_no))
                old_no += 1
            else:
                hunk.append((" ", raw[1:], old_no, new_no))
                old_no += 1
                new_no += 1
    return out


class Change:
    """One changed file as the detectors read it."""

    def __init__(self, entry, hunks, ctx):
        self.path = entry["path"]
        self.change = entry["change"]
        self.old = entry.get("from") or self.path
        self.hunks = hunks
        self.ctx = ctx
        self._head = self._base = False

    @property
    def deleted(self):
        return self.change == "deleted"

    @property
    def added_file(self):
        return self.change in ("added", "copied")

    def added(self):
        return [(n, t) for h in self.hunks for op, t, _, n in h if op == "+"]

    def removed(self):
        return [(o, t, n) for h in self.hunks for op, t, o, n in h if op == "-"]

    def blocks(self):
        """The runs of removed and added lines, between context lines: each
        one edit, a list of (op, text, old line, new line)."""
        out = []
        for h in self.hunks:
            run = []
            for item in h:
                if item[0] == " ":
                    if run:
                        out.append(run)
                    run = []
                else:
                    run.append(item)
            if run:
                out.append(run)
        return out

    def head(self):
        """The head content as text, None when deleted, binary or unreadable."""
        if self._head is False:
            self._head = None if self.deleted else self.ctx.head_text(self.path)
        return self._head

    def base(self):
        """The base content as text, None for an added file or a binary one."""
        if self._base is False:
            self._base = None if self.added_file else self.ctx.base_text(self.old)
        return self._base

    def unreadable(self):
        """Why its content can't be read, or None."""
        if self.deleted:
            return None if self.ctx.base_text(self.old) is not None else "binary or unreadable at the base"
        if self.head() is None:
            return self.ctx.head_problem(self.path)
        return None

    def head_line(self, n):
        """A line number that opens in the head file, clamped."""
        text = self.head()
        if text is None or n is None:
            return None
        count = max(len(text.rstrip("\n").split("\n")), 1)
        return max(1, min(n, count))


class Context:
    """What the detectors read: the changed files, the head tree, the base
    blobs, the tools found, a word search at the base."""

    def __init__(self, entries, patch_bytes, head_dir, read_base, mentions_base, tools, work_dir):
        diffs = parse_patch(patch_bytes)
        self.head_dir, self.read_base, self.mentions_base = head_dir, read_base, mentions_base
        self.tools = {t["name"]: t for t in tools}
        self.work_dir = work_dir
        self._base_cache, self._mentions = {}, {}
        self.changes = [Change(e, diffs.get(e["path"], []), self) for e in entries]
        self.paths = {c.path for c in self.changes}

    def head_problem(self, path):
        full = os.path.join(self.head_dir, path)
        if not os.path.isfile(full) or os.path.islink(full):
            return "not a regular file in the head tree"
        return "binary or not UTF-8 text"

    def head_text(self, path):
        full = os.path.join(self.head_dir, path)
        if not os.path.isfile(full) or os.path.islink(full):
            return None
        try:
            with open(full, "rb") as fh:
                data = fh.read(MAX_BYTES * 4)
        except OSError:
            return None
        return decode(data)

    def base_text(self, path):
        if path not in self._base_cache:
            data = self.read_base(path)
            self._base_cache[path] = decode(data) if data is not None else None
        return self._base_cache[path]

    def mentioned_at_base(self, word):
        if word not in self._mentions:
            self._mentions[word] = bool(self.mentions_base(word))
        return self._mentions[word]

    def tool(self, name):
        t = self.tools.get(name)
        return t if t and t.get("found") else None


def decode(data):
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def output(name, version, content, applies, covered, not_covered, signals, tool=None, heuristic=True,
           gaps=(), **extra):
    out = {"detector": name, "version": version, "content": content,
           "applies_to": [escape(p) for p in applies], "tool": tool, "heuristic": heuristic,
           "covered": covered, "not_covered": not_covered, "signals": signals, "gaps": list(gaps)}
    out.update(extra)
    return out


def signal(path, kind, reason, line=None, text=None):
    s = {"path": path, "kind": kind, "reason": reason}
    if line is not None:
        s["line"] = line
    if text:
        s["excerpt"] = excerpt(text)
    return s


def run_tool(command, args, cwd):
    """(return code, stdout, stderr) of a tool, or (None, "", why) when it
    could not start or timed out."""
    path = shutil.which(command)
    if not path:
        return None, "", "%s not found" % command
    try:
        done = subprocess.run([path] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, timeout=TOOL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, "", str(e)
    return done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")


def first_line(text):
    return next((line.strip() for line in str(text).split("\n") if line.strip()), "no output")


# --- Migrations -----------------------------------------------------------------

MIGRATION_KINDS = [
    (re.compile(r"(^|/)prisma/schema\.prisma$"), "prisma-schema"),
    (re.compile(r"(^|/)database/migrations/[^/]+\.php$"), "laravel"),
    (re.compile(r"(^|/)(migrations|Migrations|DoctrineMigrations)/(.+/)?Version\w*\.php$"), "doctrine"),
    (re.compile(r"(^|/)(alembic|migrations)/versions/(?!__init__\.py$)[^/]+\.py$"), "alembic"),
    (re.compile(r"(^|/)migrations/\d{4}_[^/]+\.py$"), "django"),
    (re.compile(r"(^|/)db/migrate/[^/]+\.rb$"), "rails"),
    (re.compile(r"(^|/)(migrations?|migrate|db/migration|schema/migrations|sql/migrations)/(.+/)?[^/]+\.sql$", re.I),
     "sql"),
    (re.compile(r"(^|/)[^/]+\.(up|down)\.sql$", re.I), "sql"),
]
FRAMEWORKS = {"laravel": "Laravel", "doctrine": "Doctrine", "alembic": "Alembic", "django": "Django", "rails": "Rails"}
SQL_FLAGS = re.I

MIGRATION_PATTERNS = [
    ("drop", "drops a table, a column or another object, or empties a table", re.compile(
        r"\b(DROP\s+(TABLE|COLUMN|SCHEMA|DATABASE|VIEW|MATERIALIZED\s+VIEW|TYPE|CONSTRAINT|INDEX|SEQUENCE)|TRUNCATE)\b"
        r"|Schema::(drop|dropIfExists)\s*\(|->drop(Column|Columns|IfExists|Foreign|Index|Unique|Primary|Timestamps"
        r"|SoftDeletes|Table)?\s*\(|\bop\.drop_(table|column|index|constraint)\s*\("
        r"|migrations\.(RemoveField|DeleteModel|RemoveIndex|RemoveConstraint)\s*\("
        r"|\b(remove_column|remove_columns|drop_table|remove_index|remove_reference|remove_timestamps|drop_join_table)\b",
        SQL_FLAGS)),
    ("rename", "renames a table or a column: code reading the old name breaks", re.compile(
        r"\bRENAME\s+(COLUMN|TO|TABLE)\b|\bsp_rename\b|->renameColumn\s*\(|Schema::rename\s*\("
        r"|\bop\.rename_table\s*\(|new_column_name\s*=|migrations\.(RenameField|RenameModel)\s*\("
        r"|\b(rename_column|rename_table)\b", SQL_FLAGS)),
    ("type-change", "changes a column's type or definition", re.compile(
        r"ALTER\s+COLUMN\s+\S+\s+(SET\s+DATA\s+)?TYPE\b|\bMODIFY\s+(COLUMN\s+)?\w|\bCHANGE\s+COLUMN\b"
        r"|\bop\.alter_column\s*\(|migrations\.AlterField\s*\(|\bchange_column\b|->change\s*\(\s*\)",
        SQL_FLAGS)),
    ("not-null", "makes a column required: existing rows and writers must provide it", re.compile(
        r"\bSET\s+NOT\s+NULL\b|\bnullable\s*=\s*False\b|\bchange_column_null\b.*\bfalse\b|\bnull:\s*false\b",
        SQL_FLAGS)),
    ("data-rewrite", "rewrites or deletes existing rows", re.compile(
        r"^\s*(UPDATE\s+\S+\s+SET|DELETE\s+FROM)\b|\bRunPython\s*\(|\bop\.execute\s*\(|DB::(statement|update|delete)\s*\("
        r"|\bexecute\s*\(?\s*[\"'%]\s*(UPDATE|DELETE)\b", SQL_FLAGS)),
]
ADD_NOT_NULL = re.compile(r"\bADD\s+(COLUMN\s+)?(IF\s+NOT\s+EXISTS\s+)?\S+[^;]*\bNOT\s+NULL\b", re.I)
HAS_DEFAULT = re.compile(r"\bDEFAULT\b", re.I)
SQUAWK_LINE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): (?P<level>\w+): (?P<rule>[\w-]+)\s*(?P<msg>.*)$")


def migration_kind(path):
    for rx, kind in MIGRATION_KINDS:
        if rx.search(path):
            return kind
    return None


def no_down(kind, change, ctx):
    """Why an added migration has no way back, or None."""
    text = change.head() or ""
    if kind in ("laravel", "doctrine"):
        return None if re.search(r"function\s+down\s*\(", text) else "no `down()` method"
    if kind == "alembic":
        m = re.search(r"^def\s+downgrade\s*\([^)]*\)[^:]*:\s*\n((?:[ \t]+.*\n?|\s*\n)*)", text, re.M)
        if not m:
            return "no `downgrade()`"
        body = [line.strip() for line in m.group(1).split("\n") if line.strip() and not line.strip().startswith("#")]
        body = [b for b in body if not re.match(r"^(\"\"\"|''').*(\"\"\"|''')$", b)]
        return "`downgrade()` does nothing" if body in ([], ["pass"]) else None
    if kind == "django":
        if re.search(r"RunPython\s*\(\s*[\w.]+\s*\)", text):
            return "`RunPython` without a reverse function"
        if "RunSQL(" in text and "reverse_sql" not in text:
            return "`RunSQL` without `reverse_sql`"
        return None
    if kind == "rails":
        if "IrreversibleMigration" in text:
            return "raises `IrreversibleMigration`"
        if re.search(r"^\s*def\s+up\b", text, re.M) and not re.search(r"^\s*def\s+down\b", text, re.M):
            return "`up` without `down`"
        return None
    if kind == "sql" and re.search(r"\.up\.sql$", change.path, re.I):
        down = re.sub(r"\.up\.sql$", ".down.sql", change.path, flags=re.I)
        if down not in ctx.paths and ctx.head_text(down) is None:
            return "no `%s` beside it" % os.path.basename(down)
    return None


def migrations(ctx, version):
    applies, covered, not_covered, signals, gaps = [], [], [], [], []
    sql_files = []
    for c in ctx.changes:
        kind = migration_kind(c.path)
        if not kind:
            continue
        applies.append(c.path)
        why = c.unreadable()
        if why:
            not_covered.append({"path": c.path, "reason": why})
            continue
        covered.append(c.path)
        if c.deleted:
            signals.append(signal(c.path, "migration-deleted",
                                  "a migration was deleted: databases that ran it keep its changes"))
            continue
        if kind == "prisma-schema":
            removed = [t for _, t, _ in c.removed() if not comment(t)]
            if removed:
                first = next(n for _, t, n in c.removed() if not comment(t))
                signals.append(signal(c.path, "schema-changed", "%d schema line(s) removed or changed: a field, a"
                                      " relation or a constraint may have changed" % len(removed),
                                      c.head_line(first), removed[0]))
            continue
        if not c.added_file and c.hunks:
            first = c.hunks[0][0][3]
            signals.append(signal(c.path, "migration-edited", "an existing migration was edited: databases that"
                                  " already ran it will not run it again", c.head_line(first)))
        if kind in FRAMEWORKS:
            signals.append(signal(c.path, "framework-migration", "%s migration: its SQL is not generated in this"
                                  " version, the contracts step reads it as code" % FRAMEWORKS[kind],
                                  1 if c.head() else None))
        for n, text in c.added():
            if comment(text):
                continue
            for kind_, what, rx in MIGRATION_PATTERNS:
                if rx.search(text):
                    signals.append(signal(c.path, kind_, what, n, text))
                    break
            else:
                if kind == "sql" and ADD_NOT_NULL.search(text) and not HAS_DEFAULT.search(text):
                    signals.append(signal(c.path, "not-null", "adds a NOT NULL column without a default:"
                                          " existing rows can't satisfy it", n, text))
        if c.added_file:
            why = no_down(kind, c, ctx)
            if why:
                signals.append(signal(c.path, "no-down", "no way back: %s" % why, 1))
        if kind == "sql":
            sql_files.append(c)
    tool = None
    if sql_files:
        squawk = ctx.tool("squawk")
        if not squawk:
            gaps.append("squawk not found on this machine: raw SQL migrations read by the heuristic only")
        else:
            tool = "squawk@%s" % squawk.get("version")
            code, out, err = run_tool(squawk.get("command", "squawk"),
                                      ["--reporter", "gcc"] + [c.path for c in sql_files], ctx.head_dir)
            parsed = [SQUAWK_LINE.match(line.strip()) for line in out.split("\n")]
            parsed = [m for m in parsed if m]
            if code not in (0, 1) or (code == 1 and not parsed):
                gaps.append("squawk failed (%s): raw SQL migrations read by the heuristic only"
                            % first_line(err or out))
                tool = None
            for m in parsed:
                path = m.group("file")
                path = os.path.relpath(path, ctx.head_dir) if os.path.isabs(path) else path
                if path in ctx.paths:
                    line = next((c.head_line(int(m.group("line"))) for c in sql_files if c.path == path), None)
                    signals.append(signal(path, "squawk:%s" % m.group("rule"),
                                          "squawk %s: %s" % (m.group("level"), m.group("msg").strip()), line))
    return output("migrations", version, True, applies, covered, not_covered, signals, tool=tool,
                  heuristic=True, gaps=gaps)


# --- Configuration --------------------------------------------------------------

ENV_FILE = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|[\w.-]+\.env(\.(example|sample|template|dist|defaults?))?"
                      r"|env\.(example|sample|template|dist))$")
CONFIG_FILE = re.compile(
    r"(^|/)(config|conf|configs|settings)/.+\.(ya?ml|json|toml|ini|php|py|js|ts|cjs|mjs|xml|properties|neon|env|conf)$"
    r"|(^|/)(settings|local_settings)\.py$"
    r"|(^|/)application(-[\w.-]+)?\.(ya?ml|properties)$"
    r"|(^|/)appsettings(\.[\w.-]+)?\.json$"
    r"|(^|/)(docker-)?compose([.-][\w.-]+)?\.ya?ml$"
    r"|(^|/)config\.(ya?ml|json|toml|ini)$")
ENV_LINE = re.compile(r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(?P<value>.*?)\s*$")
VAR = r"(?P<name>[A-Z][A-Z0-9_]{1,})"
ENV_READS = [re.compile(p) for p in (
    r"""os\.environ\[\s*['"]%s['"]\s*\]""" % VAR,
    r"""os\.(?:environ\.get|getenv)\(\s*['"]%s['"]\s*\)""" % VAR,
    r"""process\.env\.%s\b(?!\s*(?:\|\||\?\?))""" % VAR,
    r"""process\.env\[\s*['"]%s['"]\s*\](?!\s*(?:\|\||\?\?))""" % VAR,
    r"""\benv\(\s*['"]%s['"]\s*\)""" % VAR,
    r"""\bgetenv\(\s*['"]%s['"]\s*\)""" % VAR,
    r"""\$_(?:ENV|SERVER)\[\s*['"]%s['"]\s*\](?!\s*\?\?)""" % VAR,
    r"""%%env\((?:[\w-]+:)*%s\)%%""" % VAR,
    r"""\$\{%s(?::?\?[^}]*)?\}""" % VAR,
    r"""\bENV\[\s*['"]%s['"]\s*\](?!\s*\|\|)""" % VAR,
    r"""\bENV\.fetch\(\s*['"]%s['"]\s*\)""" % VAR,
    r"""\bSystem\.getenv\(\s*"%s"\s*\)""" % VAR,
    r"""\bos\.Getenv\(\s*"%s"\s*\)""" % VAR,
)]


def env_pairs(text):
    """{key: (value, line)} of a dotenv-style file."""
    out = {}
    for n, line in enumerate((text or "").split("\n"), 1):
        if comment(line):
            continue
        m = ENV_LINE.match(line)
        if m:
            out.setdefault(m.group("key"), (m.group("value").strip("'\""), n))
    return out


def env_reads(text):
    names = []
    for rx in ENV_READS:
        for m in rx.finditer(text):
            if m.group("name") not in names:
                names.append(m.group("name"))
    return names


def new_required_vars(c, ctx):
    """[(line, name, text)]: environment variables an added line reads with
    no default, read nowhere at the base."""
    out, seen = [], set()
    base_text = c.base() or ""
    for n, text in c.added():
        if comment(text):
            continue
        for name in env_reads(text):
            if name in seen or re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % name, base_text) \
                    or ctx.mentioned_at_base(name):
                continue
            seen.add(name)
            out.append((n, name, text))
    return out


def config(ctx, version):
    applies, covered, not_covered, signals = [], [], [], []
    for c in ctx.changes:
        env_file = bool(ENV_FILE.search(c.path))
        if not (env_file or CONFIG_FILE.search(c.path)):
            if CODE_EXT.search(c.path) and not c.deleted and c.head() is not None:
                for n, name, text in new_required_vars(c, ctx):
                    signals.append(signal(c.path, "env-required", "reads environment variable `%s` with no"
                                          " default, mentioned nowhere at the base" % name, n, text))
            continue
        applies.append(c.path)
        why = c.unreadable()
        if why:
            not_covered.append({"path": c.path, "reason": why})
            continue
        covered.append(c.path)
        if env_file:
            base, head = env_pairs(c.base()), env_pairs(c.head())
            for key, (value, n) in head.items():
                if key not in base:
                    signals.append(signal(c.path, "env-added", "new variable `%s`%s" % (
                        key, " with no default value" if not value else ""), n))
                elif base[key][0] != value:
                    signals.append(signal(c.path, "env-default-changed", "the default of `%s` changed" % key, n))
            for key in base:
                if key not in head:
                    signals.append(signal(c.path, "env-removed", "variable `%s` removed" % key))
            continue
        if c.deleted:
            signals.append(signal(c.path, "config-deleted", "a configuration file was deleted"))
            continue
        for n, name, text in new_required_vars(c, ctx):
            signals.append(signal(c.path, "env-required", "reads environment variable `%s` with no default,"
                                  " mentioned nowhere at the base" % name, n, text))
        removed = [(t, n) for _, t, n in c.removed() if not comment(t)]
        added = [(n, t) for n, t in c.added() if not comment(t)]
        if removed:
            signals.append(signal(c.path, "config-changed", "%d existing configuration line(s) removed or changed"
                                  % len(removed), c.head_line(removed[0][1]), removed[0][0]))
        elif added and not c.added_file:
            signals.append(signal(c.path, "config-added", "%d configuration line(s) added: a new setting or"
                                  " flag" % len(added), added[0][0], added[0][1]))
    return output("config", version, True, applies, covered, not_covered, signals)


# --- Routes -----------------------------------------------------------------------

ROUTE_FILE = re.compile(
    r"(^|/)routes(/[^/]+)*/[^/]+\.(php|js|ts|mjs|cjs|py|rb)$"
    r"|(^|/)config/routes(\.[\w-]+)?\.(ya?ml|php|xml|rb)$|(^|/)config/routes/.+\.(ya?ml|php|xml)$"
    r"|(^|/)urls\.py$"
    r"|(^|/)(routes|router|routing)\.(php|js|ts|mjs|cjs|py|rb|ya?ml)$"
    r"|(^|/)[\w.-]+\.routes\.(ts|js)$")
FILE_ROUTE = re.compile(r"(^|/)app/(.+/)?route\.(ts|js|tsx|jsx)$|(^|/)pages/api/.+\.(ts|js|tsx|jsx)$")
ROUTE_LINE = re.compile(
    r"Route::\w+\s*\("
    r"|\b(re_)?path\s*\(\s*r?['\"]|\burl\s*\(\s*r?['\"]"
    r"|^\s*(get|post|put|patch|delete|match|resources?|root|namespace|scope|mount)\b\s*[('\":]"
    r"|\b(app|router|route|server|api|fastify|bp|blueprint|routes)\.(get|post|put|patch|delete|all|route|use|head"
    r"|options)\s*\("
    r"|@\w+\.(route|get|post|put|patch|delete|api_route|websocket)\s*\("
    r"|#\[Route\s*\(|@Route\s*\("
    r"|^\s*path\s*:\s*\S|\bpath\s*:\s*['\"`]"
    r"|@(Get|Post|Put|Patch|Delete|All|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)"
    r"\s*\("
    r"|\bexport\s+(async\s+)?(function|const)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")
ROUTE_IN_CODE = re.compile(
    r"#\[Route\s*\(|@Route\s*\(|@\w+\.(route|get|post|put|patch|delete|api_route|websocket)\s*\("
    r"|@(Get|Post|Put|Patch|Delete|All|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)"
    r"\s*\(|\b(app|router)\.(get|post|put|patch|delete|all)\s*\(\s*['\"`]/")


def route_hunks(c, rx, added=False):
    """[signal] for the edits of a file that remove or change route lines,
    and add them when `added`."""
    out = []
    for hunk in c.blocks():
        gone = [(t, n) for op, t, _, n in hunk if op == "-" and not comment(t) and rx.search(t)]
        new = [(t, n) for op, t, _, n in hunk if op == "+" and not comment(t) and rx.search(t)]
        if gone and new:
            out.append(signal(c.path, "route-changed", "%d route line(s) changed" % len(gone),
                              c.head_line(new[0][1]), gone[0][0]))
        elif gone:
            out.append(signal(c.path, "route-removed", "%d route line(s) removed" % len(gone),
                              c.head_line(gone[0][1]), gone[0][0]))
        elif new and added:
            out.append(signal(c.path, "route-added", "%d route line(s) added: new surface, not a break"
                              % len(new), new[0][1], new[0][0]))
    return out


def routes(ctx, version):
    applies, covered, not_covered, signals = [], [], [], []
    for c in ctx.changes:
        file_route = bool(FILE_ROUTE.search(c.path) or FILE_ROUTE.search(c.old))
        if not (file_route or ROUTE_FILE.search(c.path) or ROUTE_FILE.search(c.old)):
            if CODE_EXT.search(c.path):
                signals += route_hunks(c, ROUTE_IN_CODE)
            continue
        applies.append(c.path)
        why = c.unreadable()
        if why:
            not_covered.append({"path": c.path, "reason": why})
            continue
        covered.append(c.path)
        if c.deleted:
            count = sum(1 for _, t, _ in c.removed() if ROUTE_LINE.search(t))
            signals.append(signal(c.path, "route-file-deleted", "a route file was deleted%s" % (
                ": its path was a route" if file_route else ", with %d route line(s)" % count)))
            continue
        if file_route and c.change == "renamed":
            signals.append(signal(c.path, "route-file-renamed", "a file-based route moved from `%s`: the old URL"
                                  " is gone" % c.old, 1))
        signals += route_hunks(c, ROUTE_LINE, added=not c.added_file)
    return output("routes", version, True, applies, covered, not_covered, signals)


# --- API contracts ------------------------------------------------------------------

OPENAPI_NAME = re.compile(r"(^|/)(openapi|swagger)[\w.-]*\.(ya?ml|json)$|\.(openapi|swagger)\.(ya?ml|json)$", re.I)
GRAPHQL_NAME = re.compile(r"\.(graphql|graphqls|gql)$", re.I)
OPENAPI_SNIFF = re.compile(r"""^\s*\{?\s*["']?(openapi|swagger)["']?\s*:""", re.M)
METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
GRAPHQL_DEF = re.compile(r"^\s*(type|input|enum|interface|union|scalar|directive|extend|schema)\b"
                         r"|^\s*\w+\s*(\([^)]*\))?\s*:\s*[\[\]\w!]+|^\s*[A-Z][A-Z0-9_]+\s*$")


def contract_kind(c):
    if GRAPHQL_NAME.search(c.path):
        return "graphql"
    if OPENAPI_NAME.search(c.path) or OPENAPI_NAME.search(c.old):
        return "openapi"
    if re.search(r"\.(ya?ml|json)$", c.path, re.I):
        for text in (c.head(), c.base()):
            if text and OPENAPI_SNIFF.search(text[:4096]):
                return "openapi"
    return None


def openapi_operations(text, path):
    """{path: {methods}} of an OpenAPI document, None when it can't be read."""
    if text is None:
        return {}
    if path.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError:
            return None
        paths = data.get("paths") if isinstance(data, dict) else None
        if not isinstance(paths, dict):
            return {}
        return {p: {m for m in (v or {}) if m in METHODS} for p, v in paths.items() if isinstance(v, dict)}
    ops, in_paths, path_indent, current = {}, False, None, None
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_paths = bool(re.match(r"^paths\s*:\s*$", line))
            path_indent, current = None, None
            continue
        if not in_paths:
            continue
        m = re.match(r"""^\s*['"]?(/[^'"]*?)['"]?\s*:\s*(\{\s*\})?\s*$""", line)
        if m and (path_indent is None or indent == path_indent):
            path_indent, current = indent, m.group(1)
            ops.setdefault(current, set())
            continue
        if current is not None and indent > (path_indent or 0):
            mm = re.match(r"^\s*(%s)\s*:" % "|".join(METHODS), line)
            if mm:
                ops[current].add(mm.group(1))
    return ops


def oasdiff_signals(c, ctx, tool):
    """[signal] from `oasdiff breaking`, or None when it could not run."""
    base_dir = os.path.join(ctx.work_dir, "base")
    base_file = os.path.join(base_dir, c.old)
    os.makedirs(os.path.dirname(base_file), exist_ok=True)
    with open(base_file, "w", encoding="utf-8") as fh:
        fh.write(c.base() or "")
    code, out, err = run_tool(tool.get("command", "oasdiff"),
                              ["breaking", base_file, os.path.join(ctx.head_dir, c.path), "--format", "json"],
                              ctx.work_dir)
    if code != 0:
        return None, first_line(err or out)
    try:
        items = json.loads(out or "[]")
    except ValueError:
        return None, "unreadable output: %s" % first_line(out)
    if isinstance(items, dict):
        items = items.get("changes") or items.get("breaking") or []
    levels = {3: "error", 2: "warning", 1: "info"}
    out_ = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        where = " ".join(x for x in (str(item.get("operation") or ""), str(item.get("path") or "")) if x)
        out_.append(signal(c.path, "oasdiff:%s" % item.get("id", "change"), "%s%s (%s)" % (
            "`%s`: " % where if where else "", item.get("text") or item.get("id"),
            levels.get(item.get("level"), item.get("level")))))
    return out_, None


def api_contracts(ctx, version):
    applies, covered, not_covered, signals, gaps = [], [], [], [], []
    tool_used, openapi_seen = None, False
    oasdiff = ctx.tool("oasdiff")
    for c in ctx.changes:
        kind = contract_kind(c)
        if not kind:
            continue
        applies.append(c.path)
        why = c.unreadable()
        if why:
            not_covered.append({"path": c.path, "reason": why})
            continue
        if c.deleted:
            covered.append(c.path)
            signals.append(signal(c.path, "contract-removed", "an API contract file was deleted"))
            continue
        if kind == "graphql":
            covered.append(c.path)
            for hunk in c.blocks():
                gone = [(t, n) for op, t, _, n in hunk if op == "-" and not comment(t) and GRAPHQL_DEF.search(t)]
                new = [(t, n) for op, t, _, n in hunk if op == "+" and not comment(t) and GRAPHQL_DEF.search(t)]
                if gone:
                    signals.append(signal(c.path, "field-changed" if new else "field-removed",
                                          "%d type or field line(s) %s" % (len(gone), "changed" if new else "removed"),
                                          c.head_line((new or gone)[0][1]), gone[0][0]))
            continue
        openapi_seen = True
        if c.added_file:
            covered.append(c.path)
            continue
        if oasdiff:
            found, problem = oasdiff_signals(c, ctx, oasdiff)
            if found is not None:
                covered.append(c.path)
                signals += found
                tool_used = "oasdiff@%s" % oasdiff.get("version")
                continue
            gaps.append("oasdiff failed on `%s` (%s): read by the heuristic" % (c.path, problem))
        before, after = openapi_operations(c.base(), c.old), openapi_operations(c.head(), c.path)
        if before is None or after is None:
            not_covered.append({"path": c.path, "reason": "not valid JSON at the %s" % (
                "base" if before is None else "head")})
            continue
        covered.append(c.path)
        for p in sorted(before):
            if p not in after:
                signals.append(signal(c.path, "path-removed", "path `%s` removed" % p))
            else:
                for m in sorted(before[p] - after[p]):
                    signals.append(signal(c.path, "operation-removed", "operation `%s %s` removed" % (m.upper(), p)))
        removed = [(t, n) for _, t, n in c.removed() if t.strip()]
        if removed:
            signals.append(signal(c.path, "contract-changed", "%d existing contract line(s) removed or changed:"
                                  " a field, a type or a constraint may have changed" % len(removed),
                                  c.head_line(removed[0][1]), removed[0][0]))
        required = [(n, t) for n, t in c.added() if re.match(r"""^\s*(-\s*)?["']?required["']?\s*:""", t)]
        if required:
            signals.append(signal(c.path, "required-added", "%d `required` line(s) added: a field may have"
                                  " become required" % len(required), required[0][0], required[0][1]))
    if openapi_seen and not oasdiff:
        gaps.append("oasdiff not found on this machine: OpenAPI files read by the heuristic only")
    return output("api-contracts", version, True, applies, covered, not_covered, signals, tool=tool_used,
                  heuristic=tool_used is None, gaps=gaps)


# --- Dependencies ---------------------------------------------------------------------

MANIFESTS = {"package.json": "npm", "composer.json": "composer", "pyproject.toml": "pyproject",
             "Pipfile": "pipfile", "Gemfile": "gemfile", "go.mod": "gomod", "Cargo.toml": "cargo"}
REQUIREMENTS = re.compile(r"(^|/)(requirements[\w.-]*\.(txt|in)|requirements/[\w.-]+\.(txt|in)|constraints\.txt)$")
LOCKFILES = {"package-lock.json": "package.json", "npm-shrinkwrap.json": "package.json", "yarn.lock": "package.json",
             "pnpm-lock.yaml": "package.json", "bun.lockb": "package.json", "bun.lock": "package.json",
             "composer.lock": "composer.json", "poetry.lock": "pyproject.toml", "uv.lock": "pyproject.toml",
             "pdm.lock": "pyproject.toml", "Pipfile.lock": "Pipfile", "Gemfile.lock": "Gemfile",
             "go.sum": "go.mod", "Cargo.lock": "Cargo.toml"}
PEP508 = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


class Unreadable(Exception):
    pass


def toml_items(text):
    """[(table, key, value)] of a TOML-like file, multi-line arrays joined.
    A heuristic: enough for dependency tables and arrays."""
    out, table, pending = [], "", None
    for raw in (text or "").split("\n"):
        line = re.sub(r"\s+#.*$", "", raw) if '"' not in raw and "'" not in raw else raw
        if pending is not None:
            pending[2] += " " + line.strip()
            if line.strip().startswith("]") or line.rstrip().endswith("]"):
                out.append(tuple(pending))
                pending = None
            continue
        if line.strip().startswith("#") or not line.strip():
            continue
        m = re.match(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*$", line)
        if m:
            table = m.group(1).replace('"', "").replace("'", "")
            continue
        m = re.match(r"""^\s*("[^"]+"|'[^']+'|[\w.-]+)\s*=\s*(.*?)\s*$""", line)
        if m:
            key, value = m.group(1).strip("\"'"), m.group(2)
            if value.startswith("[") and value.count("[") > value.count("]"):
                pending = [table, key, value]
            else:
                out.append((table, key, value))
    return out


def array_strings(value):
    return re.findall(r"""["']([^"']+)["']""", value)


def parse_manifest(kind, text):
    """({name: spec}, {runtime key: value}) of a manifest; raises Unreadable."""
    deps, runtime = {}, {}
    if text is None:
        return deps, runtime
    if kind in ("npm", "composer"):
        try:
            data = json.loads(text)
        except ValueError as e:
            raise Unreadable("not valid JSON: %s" % e)
        if not isinstance(data, dict):
            raise Unreadable("not a JSON object")
        sections = (["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]
                    if kind == "npm" else ["require", "require-dev"])
        for sec in sections:
            for name, spec in (data.get(sec) or {}).items() if isinstance(data.get(sec), dict) else []:
                if kind == "composer" and (name == "php" or name.startswith("ext-")):
                    runtime[name] = str(spec)
                else:
                    deps[name] = "%s (%s)" % (spec, sec)
        if kind == "npm":
            for k, v in (data.get("engines") or {}).items() if isinstance(data.get("engines"), dict) else []:
                runtime["engines.%s" % k] = str(v)
        return deps, runtime
    if kind == "requirements":
        for line in text.split("\n"):
            line = line.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            m = PEP508.match(line)
            if m:
                deps[m.group(1).lower()] = m.group(3).strip() or "any"
        return deps, runtime
    if kind == "gemfile":
        for line in text.split("\n"):
            m = re.match(r"""^\s*gem\s+['"]([^'"]+)['"]\s*(?:,\s*(.*))?$""", line)
            if m:
                deps[m.group(1)] = (m.group(2) or "any").strip()
            m = re.match(r"""^\s*ruby\s+['"]([^'"]+)['"]""", line)
            if m:
                runtime["ruby"] = m.group(1)
        return deps, runtime
    if kind == "gomod":
        block = False
        for line in text.split("\n"):
            s = line.split("//", 1)[0].strip()
            if re.match(r"^require\s*\($", s):
                block = True
                continue
            if block and s == ")":
                block = False
                continue
            m = re.match(r"^(?:require\s+)?(\S+)\s+(v\S+)", s) if block or s.startswith("require ") else None
            if m:
                deps[m.group(1)] = m.group(2)
            m = re.match(r"^(go|toolchain)\s+(\S+)$", s)
            if m:
                runtime[m.group(1)] = m.group(2)
        return deps, runtime
    for table, key, value in toml_items(text):
        if kind == "pyproject":
            if table == "project" and key in ("dependencies",):
                for spec in array_strings(value):
                    m = PEP508.match(spec)
                    if m:
                        deps[m.group(1).lower()] = m.group(3).strip() or "any"
            elif table == "project" and key == "requires-python":
                runtime["requires-python"] = value.strip("\"'")
            elif table in ("project.optional-dependencies", "dependency-groups"):
                for spec in array_strings(value):
                    m = PEP508.match(spec)
                    if m:
                        deps[m.group(1).lower()] = "%s (%s)" % (m.group(3).strip() or "any", key)
            elif re.match(r"^tool\.poetry\.(group\.[\w-]+\.)?(dev-)?dependencies$", table):
                if key == "python":
                    runtime["python"] = value.strip("\"'")
                else:
                    deps[key.lower()] = value.strip("\"'")
        elif kind == "pipfile":
            if table in ("packages", "dev-packages"):
                deps[key.lower()] = value.strip("\"'")
            elif table == "requires":
                runtime[key] = value.strip("\"'")
        elif kind == "cargo":
            if re.match(r"^(target\..+\.)?(dev-|build-)?dependencies$", table):
                deps[key] = value.strip("\"'")
            elif re.match(r"^(target\..+\.)?(dev-|build-)?dependencies\.(.+)$", table):
                name = re.match(r"^(?:target\..+\.)?(?:dev-|build-)?dependencies\.(.+)$", table).group(1)
                if key == "version":
                    deps[name] = value.strip("\"'")
                else:
                    deps.setdefault(name, "table")
            elif table == "package" and key == "rust-version":
                runtime["rust-version"] = value.strip("\"'")
    return deps, runtime


def major(spec):
    m = re.search(r"(\d+)", str(spec))
    return int(m.group(1)) if m else None


def line_of(text, name):
    if not text:
        return None
    rx = re.compile(r"""(^|["'\s/])%s(["'\s=:<>~!^,\[]|$)""" % re.escape(name))
    for n, line in enumerate(text.split("\n"), 1):
        if rx.search(line):
            return n
    return None


def dependencies(ctx, version):
    applies, covered, not_covered, signals = [], [], [], []
    changed_manifests = set()
    for c in ctx.changes:
        name = os.path.basename(c.path)
        if name in MANIFESTS or REQUIREMENTS.search(c.path):
            changed_manifests.add(c.path)
    for c in ctx.changes:
        name = os.path.basename(c.path)
        kind = MANIFESTS.get(name) or ("requirements" if REQUIREMENTS.search(c.path) else None)
        lock_of = LOCKFILES.get(name)
        if not kind and not lock_of:
            continue
        applies.append(c.path)
        if lock_of:
            if c.unreadable() and not c.deleted:
                not_covered.append({"path": c.path, "reason": c.unreadable()})
                continue
            covered.append(c.path)
            manifest = os.path.join(os.path.dirname(c.path), lock_of) if os.path.dirname(c.path) else lock_of
            plus, minus = len(c.added()), len(c.removed())
            if c.deleted:
                reason = "lockfile deleted: installs stop being reproducible"
            elif manifest in changed_manifests:
                reason = "lockfile changed (+%d/-%d lines) with its manifest `%s`" % (plus, minus, manifest)
            else:
                reason = ("lockfile changed (+%d/-%d lines) without its manifest `%s` changing: versions moved"
                          " under unchanged constraints" % (plus, minus, manifest))
            signals.append(signal(c.path, "lockfile-changed", reason, c.head_line(1) if not c.deleted else None))
            continue
        why = c.unreadable()
        if why:
            not_covered.append({"path": c.path, "reason": why})
            continue
        try:
            before = parse_manifest(kind, c.base())
            after = parse_manifest(kind, c.head())
        except Unreadable as e:
            not_covered.append({"path": c.path, "reason": str(e)})
            continue
        covered.append(c.path)
        if c.deleted:
            signals.append(signal(c.path, "manifest-deleted", "a dependency manifest was deleted, with %d"
                                  " dependencies" % len(before[0])))
            continue
        head = c.head()
        (b_deps, b_run), (h_deps, h_run) = before, after
        for dep in sorted(h_deps):
            if dep not in b_deps:
                signals.append(signal(c.path, "dependency-added", "new dependency `%s` %s" % (dep, h_deps[dep]),
                                      line_of(head, dep)))
            elif b_deps[dep] != h_deps[dep]:
                bump = major(b_deps[dep]) != major(h_deps[dep]) and None not in (major(b_deps[dep]), major(h_deps[dep]))
                signals.append(signal(c.path, "dependency-changed", "`%s` %s -> %s%s" % (
                    dep, b_deps[dep], h_deps[dep], ", a new major version" if bump else ""), line_of(head, dep)))
        for dep in sorted(b_deps):
            if dep not in h_deps:
                signals.append(signal(c.path, "dependency-removed", "dependency `%s` removed" % dep))
        for key in sorted(set(b_run) | set(h_run)):
            if b_run.get(key) != h_run.get(key):
                signals.append(signal(c.path, "runtime-changed", "runtime constraint `%s` %s -> %s" % (
                    key, b_run.get(key, "none"), h_run.get(key, "none")), line_of(head, key.split(".")[-1])))
        if not c.added_file and not any(sg["path"] == c.path for sg in signals) and (c.added() or c.removed()):
            first = (c.added() or [(c.removed()[0][2], None)])[0][0]
            signals.append(signal(c.path, "manifest-changed", "the manifest changed outside its dependencies"
                                  " (scripts, entry points, metadata): %d line(s) added, %d removed"
                                  % (len(c.added()), len(c.removed())), c.head_line(first)))
    return output("dependencies", version, True, applies, covered, not_covered, signals)


# --- Assertions -----------------------------------------------------------------------

TEST_EXT = r"\.(py|js|jsx|ts|tsx|mjs|cjs|php|rb|go|java|kt|cs|ex|exs|swift|scala)$"
TEST_FILE = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|testing)/(.+/)?[^/]+" + TEST_EXT
    + r"|(^|/)(test_[^/]+\.py|[^/]+_test\.(py|go|rb|exs)|[^/]+\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)"
      r"|[^/]+Tests?\.(php|java|kt|cs|swift|scala)|[^/]+_spec\.rb|conftest\.py)$")
ASSERTION = re.compile(
    r"\bassert\w*\b|\bexpect\s*\(|\.should\b|\.to(Be|Equal|StrictEqual|Have|Throw|Match|Contain|Include)\w*\s*\("
    r"|\$this->(assert|expect)\w*\s*\(|\b(self|static|parent)::assert\w+\s*\(|\bAssert::\w+\s*\("
    r"|\bt\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\s*\(|\b(assert|require)\.\w+\s*\("
    r"|\brefute\w*\b|\.to(_not)?\s*\(?\s*(eq|eql|equal|be|include|match|raise_error|change|have)\b|\bis_expected\b"
    r"|\bpytest\.(raises|warns|approx)\b|\bassertThat\s*\(|\bAssert\.\w+\s*\(|\bverify\s*\(")
SKIP = re.compile(
    r"@pytest\.mark\.(skip|skipif|xfail)\b|@unittest\.(skip|skipIf|skipUnless|expectedFailure)\b"
    r"|\bself\.skipTest\s*\(|\bpytest\.(skip|xfail|importorskip)\s*\("
    r"|\b(xit|xdescribe|xtest|xcontext|xspecify)\s*\(|\b(it|test|describe|context|suite|specify)\.(skip|todo)\s*\("
    r"|\$this->mark(TestSkipped|TestIncomplete)\s*\(|#\[(Skip|Ignore)\b|@(Disabled|Ignore|Skip)\b"
    r"|\bt\.Skip(f|Now)?\s*\(|^\s*(skip|pending)\b[\s(\"']|\bskip:\s*true\b")
FOCUS = re.compile(r"\b(it|test|describe|context)\.only\s*\(|\b(fit|fdescribe|fcontext)\s*\(|@pytest\.mark\.only\b")


def is_test(path):
    return bool(TEST_FILE.search(path))


def assertions(ctx, version):
    applies, covered, not_covered, signals = [], [], [], []
    for c in ctx.changes:
        if not is_test(c.path):
            continue
        applies.append(c.path)
        why = c.unreadable()
        if why:
            not_covered.append({"path": c.path, "reason": why})
            continue
        covered.append(c.path)
        if c.deleted:
            count = sum(1 for _, t, _ in c.removed() if not comment(t) and ASSERTION.search(t))
            signals.append(signal(c.path, "test-deleted", "a test file was deleted, with %d assertion line(s)" % count))
            continue
        other = []
        for hunk in c.blocks():
            gone = [(t, n) for op, t, _, n in hunk if op == "-" and not comment(t) and ASSERTION.search(t)]
            new = [(t, n) for op, t, _, n in hunk if op == "+" and not comment(t) and ASSERTION.search(t)]
            for op, t, _, n in hunk:
                if op == "+" and not comment(t) and SKIP.search(t):
                    signals.append(signal(c.path, "skip-added", "a skip marker was added", n, t))
                elif op == "+" and not comment(t) and FOCUS.search(t):
                    signals.append(signal(c.path, "focus-added", "a focus marker was added: the other tests stop"
                                          " running", n, t))
            if c.added_file:
                continue
            if gone and new:
                signals.append(signal(c.path, "assertion-modified", "%d assertion line(s) changed" % len(gone),
                                      new[0][1], gone[0][0]))
            elif gone:
                signals.append(signal(c.path, "assertion-removed", "%d assertion line(s) removed" % len(gone),
                                      c.head_line(gone[0][1]), gone[0][0]))
            else:
                other += [(t, n) for op, t, _, n in hunk if op == "-" and not comment(t)]
        if other:
            signals.append(signal(c.path, "test-code-changed", "%d existing test line(s) removed or changed outside"
                                  " assertions: what the test sets up may have changed" % len(other),
                                  c.head_line(other[0][1]), other[0][0]))
    return output("assertions", version, True, applies, covered, not_covered, signals)


# --- Fan-in -----------------------------------------------------------------------------

DEFS = {
    "py": [r"^\s*(?:async\s+)?def\s+(?P<name>[A-Za-z]\w*)\s*\(", r"^\s*class\s+(?P<name>[A-Za-z]\w*)\b"],
    "js": [r"^\s*export\s+(?:default\s+)?(?:declare\s+)?(?:async\s+)?(?:abstract\s+)?"
           r"(?:function\*?|class|const|let|var|interface|type|enum)\s+(?P<name>[A-Za-z_$][\w$]*)"],
    "php": [r"^\s*(?:(?:final|abstract|static|public)\s+)*function\s+(?P<name>[A-Za-z_]\w*)\s*\(",
            r"^\s*(?:(?:final|abstract|readonly)\s+)*(?:class|interface|trait|enum)\s+(?P<name>[A-Za-z_]\w*)"],
    "rb": [r"^\s*def\s+(?:self\.)?(?P<name>[A-Za-z]\w*[?!]?)", r"^\s*(?:class|module)\s+(?P<name>[A-Z]\w*)"],
    "go": [r"^func\s+(?:\([^)]*\)\s*)?(?P<name>[A-Z]\w*)\s*[\[(]", r"^type\s+(?P<name>[A-Z]\w*)\b"],
    "jvm": [r"\bpublic\s+(?:(?:static|final|abstract|sealed|partial)\s+)*(?:class|interface|enum|record|struct)\s+"
            r"(?P<name>[A-Za-z_]\w*)",
            r"\bpublic\s+(?:(?:static|final|abstract|override|virtual|async|synchronized)\s+)*[\w<>\[\],.?]+\s+"
            r"(?P<name>[A-Za-z_]\w*)\s*\(",
            r"^\s*(?:(?:override|open|suspend|inline)\s+)*fun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(?P<name>[A-Za-z_]\w*)\s*\("],
    "rs": [r"^\s*pub\s+(?:async\s+)?(?:fn|struct|enum|trait|type|const|static|mod)\s+(?P<name>[A-Za-z_]\w*)"],
    "ex": [r"^\s*def\s+(?P<name>[a-z_]\w*[?!]?)", r"^\s*defmodule\s+(?P<name>[\w.]+)"],
}
LANG = {"py": "py", "js": "js", "jsx": "js", "ts": "js", "tsx": "js", "mjs": "js", "cjs": "js", "php": "php",
        "rb": "rb", "go": "go", "java": "jvm", "kt": "jvm", "kts": "jvm", "cs": "jvm", "scala": "jvm",
        "swift": "jvm", "rs": "rs", "ex": "ex", "exs": "ex"}
DEF_RES = {k: [re.compile(p) for p in v] for k, v in DEFS.items()}
PRIVATE = re.compile(r"\b(private|protected|internal)\b")
COMMON = {"main", "init", "run", "get", "set", "call", "index", "test", "setup", "handle", "create", "update",
          "delete", "save", "load", "new", "from", "string", "value", "data", "name", "type", "default", "render",
          "build", "execute", "process", "apply", "show", "list", "find", "close", "open", "read", "write", "start",
          "stop", "reset", "clear", "next", "size", "length", "toString", "constructor", "Meta", "Config", "handler",
          "parse", "format", "check", "validate", "send", "add", "remove", "help"}
MAX_REFS = 5


def definitions(lang, text):
    """The public symbol a line defines, or None."""
    if PRIVATE.search(text) and lang in ("php", "jvm"):
        return None
    for rx in DEF_RES[lang]:
        m = rx.search(text)
        if m:
            return m.group("name")
    return None


def enclosing(lang, head_lines, n):
    """The nearest public definition at or above line n of the head."""
    for i in range(min(n, len(head_lines)) - 1, -1, -1):
        name = definitions(lang, head_lines[i])
        if name:
            return name, i + 1
    return None, None


def fan_in(ctx, version):
    covered, symbols = [], []
    for c in ctx.changes:
        ext = os.path.splitext(c.path)[1].lstrip(".").lower()
        lang = LANG.get(ext)
        if not lang or is_test(c.path) or c.added_file:
            continue
        head = c.head()
        if head is None and not c.deleted:
            continue
        covered.append(c.path)
        head_lines = (head or "").split("\n")
        found = {}
        removed = {}
        for _, t, _ in c.removed():
            name = definitions(lang, t)
            if name:
                removed.setdefault(name, t)
        added = {}
        for n, t in c.added():
            name = definitions(lang, t)
            if name:
                added.setdefault(name, n)
        for name, text in removed.items():
            if name in added:
                found[name] = ("signature", added[name])
                continue
            line = next((i for i, h in enumerate(head_lines, 1) if definitions(lang, h) == name), None)
            found[name] = ("signature", line) if line else ("removed", None)
        if head is not None:
            for n, _ in c.added():
                name, line = enclosing(lang, head_lines, n)
                if name and name not in found and name not in added:
                    found[name] = ("body", line)
            for _, t, n in c.removed():
                name, line = enclosing(lang, head_lines, n)
                if name and name not in found and name not in added:
                    found[name] = ("body", line)
        for name, (change, line) in found.items():
            symbols.append({"path": c.path, "symbol": name, "change": change, "line": line})
    countable = sorted({s["symbol"] for s in symbols if len(s["symbol"]) > 3 and s["symbol"] not in COMMON})
    refs = count_refs(ctx, countable) if countable else {"": (0,)}
    scanned = refs.pop("")[0]
    signals = []
    for s in symbols:
        if s["symbol"] in refs:
            s["fan_in"], s["refs"] = refs[s["symbol"]][0], refs[s["symbol"]][1]
        else:
            s["fan_in"], s["refs"] = "unknown", []
            s["why"] = "too short or too common a name to count"
        if s["change"] in ("removed", "signature") and s["fan_in"] not in ("unknown", 0):
            what = "removed" if s["change"] == "removed" else "changed its signature"
            signals.append(signal(s["path"], "symbol-removed" if s["change"] == "removed" else "symbol-signature",
                                  "public `%s` %s, %d reference(s) outside the diff" % (s["symbol"], what, s["fan_in"]),
                                  s["line"]))
        if s["line"] is None:
            del s["line"]
    return output("fan-in", version, False, covered, covered, [], signals, heuristic=True,
                  symbols=symbols, scanned=scanned)


def count_refs(ctx, names):
    """{name: (references outside the diff, [path:line, ...])}, and "" ->
    (files scanned,)."""
    rx = re.compile(r"(?<![\w$])(%s)(?![\w$])" % "|".join(re.escape(n) for n in names))
    counts = {n: [0, []] for n in names}
    scanned = 0
    for d, dirs, files in os.walk(ctx.head_dir):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for name in sorted(files):
            full = os.path.join(d, name)
            rel = os.path.relpath(full, ctx.head_dir).replace(os.sep, "/")
            if rel in ctx.paths or not CODE_EXT.search(name):
                continue
            try:
                if os.path.getsize(full) > MAX_BYTES:
                    continue
                with open(full, "rb") as fh:
                    text = decode(fh.read())
            except OSError:
                continue
            if text is None:
                continue
            scanned += 1
            for n, line in enumerate(text.split("\n"), 1):
                if comment(line):
                    continue
                for m in rx.finditer(line):
                    entry = counts[m.group(1)]
                    entry[0] += 1
                    if len(entry[1]) < MAX_REFS:
                        entry[1].append("%s:%d" % (rel, n))
    out = {n: (v[0], v[1]) for n, v in counts.items()}
    out[""] = (scanned,)
    return out


# --- All of them ------------------------------------------------------------------------

DETECTORS = [("migrations", migrations), ("config", config), ("routes", routes),
             ("api-contracts", api_contracts), ("dependencies", dependencies), ("assertions", assertions),
             ("fan-in", fan_in)]


def run_all(ctx, version):
    """[(name, output)] of every detector, in a fixed order."""
    os.makedirs(ctx.work_dir, exist_ok=True)
    try:
        return [(name, fn(ctx, version)) for name, fn in DETECTORS]
    finally:
        shutil.rmtree(ctx.work_dir, ignore_errors=True)
