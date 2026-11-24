"""The TypeScript adapter: what the review reads in TypeScript and JavaScript
code without running Node.

- `parse`: the declarations of one file (its imports, its exports, and the
  functions, classes, interfaces, type aliases, enums and variables they
  name), from a lexer that blanks comments, strings, template literals,
  regular expressions and JSX. A file the lexer can't finish raises
  `ParseError`: the detectors then say they could not cover it. A file
  that exports only through CommonJS (`module.exports`, `exports.x`) has
  `cjs_only`: its imports are read, its API is not in this version.
- `api_changes`: the signature-level diff of a file's exports between its
  base and head, labelled heuristic by its detector. Types are compared as
  written, spaces aside, so `string | number` and `number | string`
  differ. Private and `#` members are not API, protected ones are
  (subclasses outside the diff see them), and a declaration marked
  `@internal` is left out, as API Extractor does.
- `symbols`, `reference`, `member_name`: the exports and members the diff
  removes or changes, for fan-in, with the pattern their references match.
- `Project`: the import graph's nodes. Which file a specifier resolves to
  (relative paths, `tsconfig.json` or `jsconfig.json` paths and baseUrl,
  workspace packages), and which module a file belongs to.

API Extractor is not run: it reads the `.d.ts` files a build writes (see
`detectors.ADAPTERS`).
"""
import bisect
import json
import posixpath
import re

EXTS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
TS_EXTS = (".ts", ".tsx", ".mts", ".cts")
NO_JSX = (".ts", ".mts", ".cts")


class ParseError(Exception):
    pass


def is_code(path):
    """A TypeScript or JavaScript code file, not a minified bundle."""
    low = path.lower()
    return low.endswith(EXTS) and not re.search(r"\.min\.[cm]?js$", low)


def language(path):
    return "typescript" if path.lower().endswith(TS_EXTS) else "javascript"


LONG_LINE, LONG_AVERAGE = 5000, 500


def minified(text):
    """The length of the longest line when the text looks minified or
    bundled (a line over 5000 characters, or 500 on average), else None."""
    lines = text.split("\n")
    longest = max(len(line) for line in lines)
    return longest if longest > LONG_LINE or len(text) / len(lines) > LONG_AVERAGE else None


def jsx_allowed(path):
    """Whether `<` in an expression can open JSX: not in `.ts`, where it is
    a type assertion."""
    return not path.lower().endswith(NO_JSX)


# --- Lexing -------------------------------------------------------------------

SPECIAL = re.compile(r"//|/\*|/|'|\"|`|\{|\}|<")
STRINGS = {"'": re.compile(r"'(?:[^'\\\n]|\\.)*'", re.S), '"': re.compile(r'"(?:[^"\\\n]|\\.)*"', re.S)}
TEMPLATE = re.compile(r"\\.|`|\$\{", re.S)
JSX_NAME = re.compile(r"[A-Za-z_$][\w$]*(?:[.:-][\w$-]+)*")
JSX_ATTR = re.compile(r"[A-Za-z_$][\w$:.-]*")
JSX_CLOSE = re.compile(r"</\s*([A-Za-z_$][\w$]*(?:[.:-][\w$-]+)*)?\s*>")
JSX_CHILD = re.compile(r"[{<]")
GENERIC_ARROW = re.compile(r"\s*(,|extends\b)")
# After these words an expression starts, so `/` opens a regular expression
# and `<` can open JSX; after any other word, a number or `)` `]`, it is an
# operator.
BEFORE_EXPR = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else",
               "yield", "await", "export", "default"}
SPACE = " \t\r\n\f\v\ufeff\u00a0"


def blank(text):
    return re.sub(r"[^\n]", " ", text)


class Lexer:
    """Blanks what can hide code or fake it, offsets and newlines kept."""

    def __init__(self, text, jsx, tags=False):
        self.t, self.n, self.jsx, self.tags = text, len(text), jsx, tags
        self.buf = list(text)
        self.docs, self.strings = [], {}

    def run(self):
        i = 0
        if self.t.startswith("\ufeff"):
            self.buf[0], i = " ", 1
        if self.t.startswith("#!", i):
            i = self.t.find("\n")
            i = self.n if i < 0 else i
            self.blank(0, i)
        self.code(i)
        return "".join(self.buf), self.docs, self.strings

    def blank(self, i, j):
        self.buf[i:j] = blank(self.t[i:j])

    def fail(self, what, i):
        raise ParseError("%s (line %d)" % (what, self.t.count("\n", 0, i) + 1))

    def expr_allowed(self, i):
        """Whether an expression can start at offset i, from what comes
        before it once comments are blanked."""
        buf, k = self.buf, i - 1
        while k >= 0 and buf[k] in SPACE:
            k -= 1
        if k < 0:
            return True
        c = buf[k]
        if c.isalnum() or c in "_$":
            j = k
            while j >= 0 and (buf[j].isalnum() or buf[j] in "_$"):
                j -= 1
            if j >= 0 and buf[j] == ".":
                return False
            return "".join(buf[j + 1:k + 1]) in BEFORE_EXPR
        return c not in ")]\"'`."

    def code(self, i, close=False):
        """Scan code from offset i to the end; with `close`, up to the `}`
        that closes a brace opened before i, whose offset it returns."""
        t, depth = self.t, 0
        while True:
            m = SPECIAL.search(t, i)
            if not m:
                if close:
                    self.fail("a `{` or `${` never closes", i)
                return self.n
            k, tok = m.start(), m.group()
            if tok == "{":
                depth += 1
                i = k + 1
            elif tok == "}":
                if close and depth == 0:
                    return k
                depth -= 1
                i = k + 1
            elif tok == "//":
                j = t.find("\n", k)
                j = self.n if j < 0 else j
                self.blank(k, j)
                i = j
            elif tok == "/*":
                j = t.find("*/", k + 2)
                if j < 0:
                    self.fail("a comment never closes", k)
                j += 2
                if t.startswith("/**", k) and j - k > 4:
                    self.docs.append((j, t[k:j]))
                self.blank(k, j)
                i = j
            elif tok in STRINGS:
                i = self.string(k)
            elif tok == "`":
                i = self.template(k)
            elif tok == "/":
                i = self.regex(k) if self.expr_allowed(k) else k + 1
            else:
                i = self.maybe_jsx(k) if self.jsx and self.expr_allowed(k) else k + 1

    def string(self, k):
        m = STRINGS[self.t[k]].match(self.t, k)
        if not m:
            self.fail("a string never closes", k)
        j = m.end()
        self.strings[k] = re.sub(r"\\(.)", r"\1", self.t[k + 1:j - 1], flags=re.S)
        self.blank(k + 1, j - 1)
        return j

    def template(self, k):
        i = k + 1
        while True:
            m = TEMPLATE.search(self.t, i)
            if not m:
                self.fail("a template literal never closes", k)
            if m.group() == "`":
                self.blank(k + 1, m.start())
                return m.end()
            i = self.code(m.end(), close=True) + 1 if m.group() == "${" else m.end()

    def regex(self, k):
        t, i, cls = self.t, k + 1, False
        while i < self.n:
            c = t[i]
            if c == "\\":
                i += 2
                continue
            if c == "\n":
                return k + 1  # a division after all
            if cls:
                cls = c != "]"
            elif c == "[":
                cls = True
            elif c == "/":
                break
            i += 1
        else:
            return k + 1
        i += 1
        while i < self.n and (t[i].isalnum() or t[i] == "_"):
            i += 1
        self.blank(k, i)
        self.buf[k] = "0"
        return i

    def maybe_jsx(self, k):
        """JSX at offset k, blanked to an operand; or k + 1 when it is not
        JSX (a generic arrow function, a type, or a tag that never closes:
        everything it touched is restored)."""
        t, j = self.t, k + 1
        if j >= self.n:
            return j
        if t[j] != ">":
            m = JSX_NAME.match(t, j)
            if not m or GENERIC_ARROW.match(t, m.end()):
                return k + 1
        docs, keep = len(self.docs), []
        try:
            end = self.element(k, keep)
        except ParseError:
            self.buf[k:] = list(t[k:])
            del self.docs[docs:]
            for key in [s for s in self.strings if s >= k]:
                del self.strings[key]
            return k + 1
        at = k
        for i, j in keep:
            self.blank(at, i)
            at = j
        self.blank(at, end)
        if not self.tags:
            self.buf[k] = "0"
        return end

    def container(self, i, keep):
        """Scan the code of a JSX `{...}` whose `{` is at i, kept as code;
        returns the offset after its `}`."""
        j = self.code(i + 1, close=True)
        keep.append((i + 1, j))
        return j + 1

    def ws(self, i):
        """The offset after the spaces and comments at i, inside a JSX tag."""
        t = self.t
        while i < self.n:
            if t[i].isspace():
                i += 1
            elif t.startswith("//", i):
                j = t.find("\n", i)
                i = self.n if j < 0 else j
            elif t.startswith("/*", i):
                j = t.find("*/", i + 2)
                if j < 0:
                    self.fail("a comment never closes", i)
                i = j + 2
            else:
                break
        return i

    def element(self, k, keep):
        t = self.t
        i = self.ws(k + 1)
        if i < self.n and t[i] == ">":
            return self.children(i + 1, "", keep)
        m = JSX_NAME.match(t, i)
        if not m:
            self.fail("not JSX", k)
        name, i = m.group(), m.end()
        if self.tags:
            keep.append((m.start(), m.end()))
        if i < self.n and t[i] == "<":  # type arguments: <Select<Option> ...>
            depth = 0
            while i < self.n:
                depth += {"<": 1, ">": -1}.get(t[i], 0)
                i += 1
                if depth == 0:
                    break
        while True:
            i = self.ws(i)
            if i >= self.n:
                self.fail("a JSX tag never closes", k)
            if t.startswith("/>", i):
                return i + 2
            c = t[i]
            if c == ">":
                return self.children(i + 1, name, keep)
            if c == "{":
                i = self.container(i, keep)
                continue
            m = JSX_ATTR.match(t, i)
            if not m:
                self.fail("not JSX", i)
            i = self.ws(m.end())
            if i < self.n and t[i] == "=":
                i = self.ws(i + 1)
                c = t[i] if i < self.n else ""
                if c in ("'", '"'):
                    j = t.find(c, i + 1)
                    if j < 0:
                        self.fail("a JSX attribute never closes", i)
                    i = j + 1
                elif c == "{":
                    i = self.container(i, keep)
                elif c == "<":
                    i = self.element(i, keep)
                else:
                    self.fail("not JSX", i)

    def children(self, i, name, keep):
        t = self.t
        while True:
            m = JSX_CHILD.search(t, i)
            if not m:
                self.fail("a JSX element never closes", i)
            j = m.start()
            if t[j] == "{":
                i = self.container(j, keep)
            elif t.startswith("</", j):
                m = JSX_CLOSE.match(t, j)
                if not m or (m.group(1) or "") != name:
                    self.fail("a JSX element closes with another tag", j)
                return m.end()
            else:
                i = self.element(j, keep)


def strip(text, jsx=True, tags=False):
    """(code, docblocks, strings): the text with comments, string and
    template contents, regular expressions and JSX blanked, offsets and
    newlines kept (a regular expression or JSX element becomes `0`, an
    operand, and the code of a JSX `{...}` stays); docblocks as [(end
    offset, text)]; string values by the offset of their opening quote.
    With `tags`, a JSX tag's name stays too, as fan-in counts it, and no
    `0` stands for the element. Raises ParseError."""
    return Lexer(text, jsx, tags).run()


# --- Parsing ------------------------------------------------------------------

TOKEN = re.compile(r"#?[A-Za-z_$\u00c0-\uffff][\w$\u00c0-\uffff]*|\d[\w.]*|'[^']*'|\"[^\"]*\"|`[^`]*`"
                   r"|\.\.\.|=>|\?\.(?!\d)|\S")
NAME = re.compile(r"^[A-Za-z_$\u00c0-\uffff][\w$\u00c0-\uffff]*$")
OPEN, CLOSE = "([{", ")]}"
INTERNAL = re.compile(r"@internal\b")
MODIFIERS = {"public", "private", "protected", "static", "readonly", "abstract", "override", "declare", "accessor",
             "async"}
VISIBILITY = ("public", "protected", "private")
# Words after which a type or an expression is not finished.
OPERATOR_WORDS = {"keyof", "typeof", "infer", "extends", "is", "asserts", "readonly", "new", "unique", "in", "of",
                  "as", "satisfies", "instanceof", "return", "await", "yield", "void", "delete", "throw", "case",
                  "else", "do", "import", "export", "default", "const", "let", "var", "function", "class"}
TYPE_OPERATORS = {"keyof", "typeof", "infer", "extends", "is", "asserts", "readonly", "new", "unique", "in", "as",
                  "satisfies"}
TYPE_GOES_ON = {"|", "&", ".", "[", "<", "=>", "extends", "?", ":", "is", "?.", "keyof", "typeof", "as"}
EXPR_GOES_ON = set(".?:=+-*/%&|^<>,!") | {"=>", "?.", "in", "instanceof", "as", "satisfies"}
CONTINUES = set("=,(.[?:+-*/%&|^!~<>{") | {"=>", "?.", "...", "new", "in", "of", "instanceof", "typeof", "return",
                                            "await", "yield", "extends", "export", "default", "declare", "case"}
STATEMENT = {"function", "class", "interface", "type", "enum", "const", "let", "var", "declare", "namespace",
             "module", "abstract", "async", "using"}


def is_name(t):
    return bool(t) and bool(NAME.match(t)) and not t.startswith("#")


def is_string(t):
    return len(t) >= 2 and t[0] in "'\"" and t[-1] == t[0]


def complete(t, in_type=False):
    """Whether a token can end an expression, or a type."""
    if not t:
        return False
    if t[0] in "'\"`" or t[0].isdigit() or t in (")", "]", "}", ">") or (t == "!" and not in_type):
        return True  # `!` ends a line only as a non-null assertion
    if t == "const" and not in_type:
        return True  # `as const`: a declaration never ends a line on `const`
    return is_name(t) and t not in (TYPE_OPERATORS if in_type else OPERATOR_WORDS)


def norm(texts):
    """A type or a default as one comparable string: tokens joined, a space
    only between two words, `;` as `,`, no trailing separator."""
    out = ""
    for t in texts:
        if out and (out[-1].isalnum() or out[-1] in "_$") and (t[0].isalnum() or t[0] in "_$'\"`"):
            out += " "
        out += "," if t == ";" else t
    out = re.sub(r",(?=[}\])>])", "", out)
    out = re.sub(r"([{(\[<=:])[|&]", r"\1", out)
    return out.lstrip("|&").rstrip(",") or None


class Unit:
    """The declarations of one TypeScript or JavaScript file."""

    def __init__(self, text, path):
        self.lines = text.split("\n")
        code, docs, strings = strip(text, jsx_allowed(path))
        self._starts = [0] + [m.end() for m in re.finditer(r"\n", code)]
        self._code, self._docs, self._strings = code, docs, strings
        self._doc_ends = [d[0] for d in docs]
        self._toks = [(m.group(0), m.start()) for m in TOKEN.finditer(code)]
        self._match = self._pairs()
        self.imports = []  # (kind, specifier, line)
        self.locals = {}  # name -> declaration
        self.exports = {}  # exported name -> declaration, or {"kind": "reexport", ...}
        self.stars = []  # (specifier, line) of `export * from`
        self.bindings = {}  # local name -> (specifier, imported name)
        self.cjs = False
        self._listed = []  # (exported, local, line) of `export { local as exported }`
        self._parse()

    @property
    def cjs_only(self):
        return self.cjs and not self.exports and not self.stars

    def text(self, line):
        return self.lines[line - 1] if line and 0 < line <= len(self.lines) else ""

    # Tokens ---------------------------------------------------------------

    def _pairs(self):
        match, stack = {}, []
        for i, (t, off) in enumerate(self._toks):
            if t in OPEN:
                stack.append(i)
            elif t in CLOSE:
                if not stack or self._toks[stack[-1]][0] != OPEN[CLOSE.index(t)]:
                    raise ParseError("a `%s` closes nothing (line %d)" % (t, self.line_of(off)))
                match[stack.pop()] = i
        if stack:
            t, off = self._toks[stack[-1]]
            raise ParseError("a `%s` never closes (line %d)" % (t, self.line_of(off)))
        return match

    def line_of(self, off):
        return bisect.bisect_right(self._starts, off)

    def line(self, i):
        return self.line_of(self._toks[min(i, len(self._toks) - 1)][1]) if self._toks else 1

    def tok(self, i):
        return self._toks[i][0] if 0 <= i < len(self._toks) else ""

    def string(self, i):
        """The value of the string token at i, or None."""
        if not is_string(self.tok(i)):
            return None
        return self._strings.get(self._toks[i][1])

    def newline_before(self, i):
        if i <= 0 or i >= len(self._toks):
            return False
        prev, off = self._toks[i - 1]
        return "\n" in self._code[off + len(prev):self._toks[i][1]]

    def end(self, i):
        """The index after the group opened at i."""
        return self._match[i] + 1

    def internal(self, i):
        """Whether a docblock right before token i says `@internal`."""
        if i >= len(self._toks):
            return False
        off = self._toks[i][1]
        k = bisect.bisect_right(self._doc_ends, off) - 1
        if k < 0:
            return False
        end, doc = self._docs[k]
        return not self._code[end:off].strip() and bool(INTERNAL.search(doc))

    def text_of(self, i):
        """Token i as a type or a default reads it: a string with its value."""
        t = self.tok(i)
        if is_string(t):
            return "'%s'" % self._strings.get(self._toks[i][1], "")
        return t

    def texts(self, i, j):
        return [self.text_of(k) for k in range(i, j)]

    # Statements ------------------------------------------------------------

    def _parse(self):
        i, n = 0, len(self._toks)
        while i < n:
            t = self.tok(i)
            if t in OPEN:
                i = self.end(i)
            elif t == "import" and self.tok(i + 1) not in ("(", "."):
                i = self._import(i)
            elif t == "export":
                i = self._export(i)
            elif t in STATEMENT and self._starts_statement(i):
                decls, nxt = self._decl(i)
                for d in decls:
                    self._local(d)
                i = nxt
            else:
                i += 1
        for exported, local, line in self._listed:
            if local in self.locals:
                self.exports[exported] = dict(self.locals[local], exported=exported)
            elif local in self.bindings:
                spec, name = self.bindings[local]
                self.exports[exported] = {"kind": "reexport", "from": spec, "name": name, "line": line,
                                          "internal": False}
            else:
                self.exports[exported] = {"kind": "value", "name": local, "line": line, "internal": False}
        self._scan_calls()

    def _starts_statement(self, i):
        if i == 0:
            return True
        prev = self.tok(i - 1)
        if prev in (";", "}"):
            return True
        return self.newline_before(i) and prev not in CONTINUES

    def _scan_calls(self):
        """Dynamic imports, `require` calls and CommonJS exports, anywhere."""
        for i, (t, _) in enumerate(self._toks):
            prev = self.tok(i - 1)
            if prev in (".", "?."):
                continue
            if t in ("import", "require") and self.tok(i + 1) == "(" and self.string(i + 2) is not None:
                self.imports.append(("dynamic" if t == "import" else "require", self.string(i + 2), self.line(i)))
            elif t == "module" and self.tok(i + 1) == "." and self.tok(i + 2) == "exports":
                self.cjs = True
            elif t == "exports" and self.tok(i + 1) == "." and is_name(self.tok(i + 2)) and self.tok(i + 3) == "=":
                self.cjs = True

    def _local(self, d):
        if not d.get("name"):
            return
        old = self.locals.get(d["name"])
        if old and old["kind"] == d["kind"] == "function":
            old["sigs"] += d["sigs"]
            old["end"] = d["end"]
        elif old and old["kind"] in ("function", "class", "enum") and d["kind"] == "namespace":
            pass  # a namespace merged into a function, class or enum adds members; the declaration stays
        elif old and old["kind"] == d["kind"] == "interface":
            old["members"].update({k: v for k, v in d["members"].items() if k not in old["members"]})
            old["extends"] += [x for x in d["extends"] if x not in old["extends"]]
        else:
            self.locals[d["name"]] = d

    def _stmt_end(self, k):
        """The index after the statement that goes on at k: its `;`, or the
        last token before a new line that does not continue it."""
        n, prev = len(self._toks), None
        while k < n:
            t = self.tok(k)
            if t == ";":
                return k + 1
            if prev is not None and self.newline_before(k) and complete(prev) and t not in EXPR_GOES_ON:
                return k
            if t in OPEN:
                k = self.end(k)
                prev = ")"
                continue
            if t in CLOSE:
                return k
            prev, k = t, k + 1
        return k

    def _semi(self, k):
        """The index after an optional `;` at k: a statement that ended."""
        return k + 1 if self.tok(k) == ";" else k

    def _import(self, i):
        k, kind, line = i + 1, "value", self.line(i)
        if self.tok(k) == "type" and self.tok(k + 1) not in ("from", ",", "="):
            kind, k = "type", k + 1
        spec = self.string(k)
        if spec is not None:
            self.imports.append(("side-effect", spec, line))
            return self._semi(k + 1)
        if is_name(self.tok(k)) and self.tok(k + 1) == "=":
            if self.tok(k + 2) == "require" and self.tok(k + 3) == "(" and self.string(k + 4) is not None:
                spec = self.string(k + 4)
                self.imports.append((kind, spec, line))
                self.bindings[self.tok(k)] = (spec, "=")
            return self._stmt_end(k + 2)
        names = []
        while k < len(self._toks) and self.tok(k) not in ("from", ";"):
            t = self.tok(k)
            if t == "{":
                names += self._specifiers(k)
                k = self.end(k)
                continue
            if t == "*" and self.tok(k + 1) == "as":
                names.append((self.tok(k + 2), "*"))
                k += 3
                continue
            if is_name(t):
                names.append((t, "default"))
            elif t != ",":
                break
            k += 1
        spec = self.string(k + 1) if self.tok(k) == "from" else None
        if spec is None:
            return k + 1
        self.imports.append((kind, spec, line))
        for local, imported in names:
            self.bindings[local] = (spec, imported)
        k += 2
        if self.tok(k) in ("with", "assert") and self.tok(k + 1) == "{":
            k = self.end(k + 1)
        return k + 1 if self.tok(k) == ";" else k

    def _specifiers(self, k):
        """[(local, imported)] of a `{ a, b as c, type d }` group."""
        out, items, cur = [], [], []
        for j in range(k + 1, self._match[k]):
            if self.tok(j) == ",":
                items.append(cur)
                cur = []
            else:
                cur.append(self.tok(j))
        items.append(cur)
        for item in items:
            if item[:1] == ["type"] and len(item) > 1 and item[1] != "as":
                item = item[1:]
            if not item:
                continue
            imported = self.string_value(item[0])
            local = item[2] if len(item) >= 3 and item[1] == "as" else imported
            out.append((local, imported))
        return out

    def string_value(self, t):
        return t[1:-1] if is_string(t) else t

    def _export(self, i):
        k, line, internal = i + 1, self.line(i), self.internal(i)
        t = self.tok(k)
        if t == "default":
            k += 1
            if self.tok(k) in ("function", "class", "abstract", "async", "interface"):
                decls, nxt = self._decl(k, anonymous=True)
                if decls:
                    d = decls[0]
                    d.update(line=line, internal=internal or d["internal"])
                    self.exports["default"] = d
                    self._local(d)
                    return nxt
            if is_name(self.tok(k)) and (self.tok(k + 1) in (";", "") or self.newline_before(k + 1)):
                self._listed.append(("default", self.tok(k), line))
                return self._semi(k + 1)
            else:
                sig = self._arrow(k)
                self.exports["default"] = {"kind": "variable" if sig else "value", "name": "default", "line": line,
                                           "internal": internal, "sigs": [sig] if sig else [], "type": None,
                                           "end": self.line(self._stmt_end(k) - 1)}
            return self._stmt_end(k)
        if t == "=":
            self.exports["="] = {"kind": "value", "name": "=", "line": line, "internal": internal}
            return self._stmt_end(k + 1)
        if t == "*":
            ns = self.tok(k + 2) if self.tok(k + 1) == "as" else None
            j = k + 3 if ns else k + 1
            spec = self.string(j + 1) if self.tok(j) == "from" else None
            if spec is None:
                return k + 1
            self.imports.append(("reexport", spec, line))
            if ns:
                self.exports[self.string_value(ns)] = {"kind": "reexport", "from": spec, "name": "*", "line": line,
                                                       "internal": internal}
            else:
                self.stars.append((spec, line))
            return self._semi(j + 2)
        if t == "type" and self.tok(k + 1) in ("{", "*"):
            return self._export(k)
        if t == "{":
            close = self.end(k)
            pairs = self._specifiers(k)
            spec = self.string(close + 1) if self.tok(close) == "from" else None
            if spec is not None:
                self.imports.append(("reexport", spec, line))
                for exported, local in pairs:
                    self.exports[exported] = {"kind": "reexport", "from": spec, "name": local, "line": line,
                                              "internal": internal}
                return self._semi(close + 2)
            for exported, local in pairs:
                self._listed.append((exported, local, line))
            return self._semi(close)
        if t == "import" and is_name(self.tok(k + 1)) and self.tok(k + 2) == "=":
            self.exports[self.tok(k + 1)] = {"kind": "value", "name": self.tok(k + 1), "line": line,
                                             "internal": internal}
            return self._stmt_end(k + 3)
        if t == "as" and self.tok(k + 1) == "namespace":
            return self._stmt_end(k + 2)
        decls, nxt = self._decl(k)
        for d in decls:
            d.update(line=line, internal=internal or d["internal"])
            self._local(d)
            if d.get("name"):
                self.exports[d["name"]] = self.locals[d["name"]]
        return nxt

    # Declarations ------------------------------------------------------------

    def _decl(self, i, anonymous=False):
        """([declaration], index after) of the declaration at token i, or
        ([], i + 1) when there is none."""
        j, abstract = i, False
        while self.tok(j) in ("declare", "abstract", "async") and self.tok(j + 1) not in ("(", "=", ":", ".", ";"):
            abstract = abstract or self.tok(j) == "abstract"
            j += 1
        w, nxt = self.tok(j), self.tok(j + 1)
        base = {"line": self.line(i), "internal": self.internal(i)}
        if w == "function":
            return self._function(j, base, anonymous)
        if w == "class":
            return self._class(j, base, abstract, anonymous)
        if w == "interface" and is_name(nxt):
            return self._interface(j, base)
        if w == "type" and is_name(nxt) and self.tok(j + 2) in ("=", "<"):
            return self._alias(j, base)
        if w == "enum" or (w == "const" and nxt == "enum"):
            return self._enum(j, base)
        if w in ("const", "let", "var", "using") and (is_name(nxt) or nxt in ("{", "[")):
            return self._variables(j, base)
        if w in ("namespace", "module") and (is_name(nxt) or is_string(nxt)):
            k = j + 1
            while self.tok(k + 1) == "." and is_name(self.tok(k + 2)):
                k += 2
            name = self.string_value("".join(self.texts(j + 1, k + 1)))
            if self.tok(k + 1) != "{":
                return [], k + 1
            close = self._match[k + 1]
            return [dict(base, kind="namespace", name=name, end=self.line(close))], close + 1
        if w == "global" and nxt == "{":
            return [], self.end(j + 1)
        return [], i + 1

    def _angles(self, k):
        """(text, index after) of the `<...>` at k, or (None, k)."""
        if self.tok(k) != "<":
            return None, k
        depth, j = 0, k
        while j < len(self._toks):
            t = self.tok(j)
            if t in OPEN:
                j = self.end(j)
                continue
            if t == "<":
                depth += 1
            elif t == ">":
                depth -= 1
                if depth == 0:
                    return norm(self.texts(k + 1, j)), j + 1
            elif t in (";",) or t in CLOSE:
                break
            j += 1
        return None, k

    def _type(self, k, stops=(), arrow=False, newline=False):
        """(text, index) of the type at token k, up to a stop token, the body
        `{` after a finished type, `=>` when `arrow`, or a new line after a
        finished type when `newline`."""
        start, angle, prev, n = k, 0, None, len(self._toks)
        while k < n:
            t = self.tok(k)
            if angle == 0:
                if t in stops or t in CLOSE or (arrow and t == "=>"):
                    break
                if t == "{" and complete(prev, True):
                    break
                if newline and prev is not None and self.newline_before(k) and complete(prev, True) \
                        and t not in TYPE_GOES_ON:
                    break
            if t in OPEN:
                k = self.end(k)
                prev = ")"
                continue
            if t == "<":
                angle += 1
            elif t == ">":
                if not angle:
                    break
                angle -= 1
            prev, k = t, k + 1
        return norm(self.texts(start, k)), k

    def _params(self, k):
        """[param] of the `(...)` group at k."""
        close, items, cur, angle, typed = self._match[k], [], [], 0, False
        j = k + 1
        while j < close:
            t = self.tok(j)
            if t in OPEN:
                cur += list(range(j, self.end(j)))
                j = self.end(j)
                continue
            if t == "," and angle == 0:
                items.append(cur)
                cur, typed = [], False
                j += 1
                continue
            if t == ":" and angle == 0:
                typed = True
            elif t == "=" and angle == 0:
                typed = False
            elif typed and t == "<":
                angle += 1
            elif typed and t == ">" and angle:
                angle -= 1
            cur.append(j)
            j += 1
        if cur:
            items.append(cur)
        return [p for p in (self._param(x) for x in items) if p]

    def _param(self, idx):
        toks = [self.text_of(j) for j in idx]
        k = 0
        while k < len(toks) and toks[k] == "@":
            k += 1
            while k < len(toks) and (is_name(toks[k]) or toks[k] == "."):
                k += 1
            if k < len(toks) and toks[k] == "(":
                close = self._match[idx[k]]
                while k < len(toks) and idx[k] <= close:
                    k += 1
        promoted = None
        while k + 1 < len(toks) and toks[k] in ("public", "private", "protected", "readonly", "override") \
                and toks[k + 1] not in (":", "?", "=", ",", ")"):
            if toks[k] in VISIBILITY:
                promoted = toks[k]
            elif promoted is None and toks[k] == "readonly":
                promoted = "public"
            k += 1
        rest = k < len(toks) and toks[k] == "..."
        k += 1 if rest else 0
        if k >= len(toks):
            return None
        if toks[k] in ("{", "["):
            close = self._match[idx[k]]
            name = "{...}" if toks[k] == "{" else "[...]"
            while k < len(toks) and idx[k] <= close:
                k += 1
        elif is_name(toks[k]):
            name = toks[k]
            k += 1
        else:
            return None
        if name == "this":
            return None
        optional = k < len(toks) and toks[k] == "?"
        k += 1 if optional else 0
        typ = None
        if k < len(toks) and toks[k] == ":":
            j = k + 1
            while j < len(toks) and toks[j] != "=":
                if toks[j] in OPEN:
                    close = self._match[idx[j]]
                    while j < len(toks) and idx[j] <= close:
                        j += 1
                    continue
                j += 1
            typ, k = norm(toks[k + 1:j]), j
        default = k < len(toks) and toks[k] == "="
        return {"name": name, "type": typ, "optional": optional or default, "rest": rest, "promoted": promoted}

    def _signature(self, k, body=True, arrow=False):
        """(signature, index after its return type) for the `<...>` or `(` at
        k: {tparams, params, returns}."""
        tparams, k = self._angles(k)
        if self.tok(k) != "(":
            return None, k
        params = self._params(k)
        k = self.end(k)
        returns = None
        if self.tok(k) == ":":
            returns, k = self._type(k + 1, stops=(";", ",") if not body else (";",), arrow=arrow, newline=True)
        return {"tparams": tparams, "params": params, "returns": returns}, k

    def _function(self, j, base, anonymous):
        k = j + 1
        if self.tok(k) == "*":
            k += 1
        name = self.tok(k) if is_name(self.tok(k)) else None
        if name is None and not anonymous:
            return [], j + 1
        sig, k = self._signature(k + 1 if name else k)
        if sig is None:
            return [], k
        sig["body"] = self.tok(k) == "{"
        end = self._match[k] if sig["body"] else k
        nxt = end + 1 if sig["body"] or self.tok(k) == ";" else k
        return [dict(base, kind="function", name=name or "default", sigs=[sig], end=self.line(end))], nxt

    def _ref(self, k):
        """(dotted name, index after it and its type arguments) at k."""
        j = k
        while self.tok(j + 1) == "." and is_name(self.tok(j + 2)):
            j += 2
        name = "".join(self.texts(k, j + 1))
        _, after = self._angles(j + 1)
        return name, after

    def _heritage(self, k, d):
        """Read `extends` and `implements` lists from k to the body `{`;
        returns the index of the `{`."""
        into = None
        while k < len(self._toks) and self.tok(k) != "{":
            t = self.tok(k)
            if t in ("extends", "implements"):
                into = d.setdefault(t, [])
                k += 1
            elif into is not None and is_name(t):
                name, k = self._ref(k)
                into.append(name)
            elif t in ("(", "["):
                k = self.end(k)
            elif t == ";":
                break
            else:
                k += 1
        return k

    def _class(self, j, base, abstract, anonymous):
        k = j + 1
        name = self.tok(k) if is_name(self.tok(k)) and self.tok(k) not in ("extends", "implements") else None
        if name is None and not anonymous:
            return [], j + 1
        k = k + 1 if name else k
        tparams, k = self._angles(k)
        d = dict(base, kind="class", name=name or "default", abstract=abstract, tparams=tparams, extends=[],
                 implements=[])
        k = self._heritage(k, d)
        if self.tok(k) != "{":
            return [], k
        close = self._match[k]
        d["members"] = self._members(k + 1, close, "class")
        d["end"] = self.line(close)
        return [d], close + 1

    def _interface(self, j, base):
        name = self.tok(j + 1)
        tparams, k = self._angles(j + 2)
        d = dict(base, kind="interface", name=name, tparams=tparams, extends=[])
        k = self._heritage(k, d)
        if self.tok(k) != "{":
            return [], k
        close = self._match[k]
        d["members"] = self._members(k + 1, close, "interface")
        d["end"] = self.line(close)
        return [d], close + 1

    def _alias(self, j, base):
        name = self.tok(j + 1)
        tparams, k = self._angles(j + 2)
        if self.tok(k) != "=":
            return [], k
        text, k = self._type(k + 1, stops=(";",), newline=True)
        d = dict(base, kind="type", name=name, tparams=tparams, text=text, end=self.line(k - 1))
        return [d], k + 1 if self.tok(k) == ";" else k

    def _enum(self, j, base):
        const = self.tok(j) == "const"
        k = j + 2 if const else j + 1
        name = self.tok(k)
        if not is_name(name) or self.tok(k + 1) != "{":
            return [], k + 1
        close = self._match[k + 1]
        members, cur, items, line = {}, [], [], None
        m = k + 2
        while m < close:
            t = self.tok(m)
            if t == ",":
                items.append((cur, line))
                cur = []
                m += 1
                continue
            if not cur:
                line = self.line(m)
            if t in OPEN:
                cur += self.texts(m, self.end(m))
                m = self.end(m)
                continue
            cur.append(self.text_of(m))
            m += 1
        if cur:
            items.append((cur, line))
        last = -1
        for item, line in items:
            key = self.string_value(item[0])
            value = norm(item[2:]) if len(item) > 2 and item[1] == "=" else None
            if value is None:
                effective = str(last + 1) if isinstance(last, int) else None
            else:
                effective = value
            last = int(effective) if effective is not None and re.match(r"^-?\d+$", effective) else None
            members[key] = {"name": key, "value": effective, "line": line}
        return [dict(base, kind="enum", name=name, const=const, members=members, end=self.line(close))], close + 1

    def _arrow(self, k):
        """The signature of the function expression at k (an arrow function
        or `function (...)`), or None."""
        if self.tok(k) == "async" and not self.newline_before(k + 1):
            k += 1
        if self.tok(k) == "function":
            k += 1
            if self.tok(k) == "*":
                k += 1
            if is_name(self.tok(k)):
                k += 1
            sig, _ = self._signature(k)
            return sig
        if is_name(self.tok(k)) and self.tok(k + 1) == "=>":
            return {"tparams": None, "params": [{"name": self.tok(k), "type": None, "optional": False, "rest": False,
                                                 "promoted": None}], "returns": None}
        if self.tok(k) not in ("(", "<"):
            return None
        sig, after = self._signature(k, arrow=True)
        return sig if sig is not None and self.tok(after) == "=>" else None

    def _expr_end(self, k, stop):
        """The index of the end of the expression at k: a `;`, a token
        `stop` accepts at depth 0, a closing bracket, or a new line that
        does not continue it."""
        prev, n = None, len(self._toks)
        while k < n:
            t = self.tok(k)
            if t == ";" or t in CLOSE or stop(k):
                return k
            if prev is not None and self.newline_before(k) and complete(prev) and t not in EXPR_GOES_ON:
                return k
            if t in OPEN:
                k = self.end(k)
                prev = ")"
                continue
            after = self._generic_call(k, prev)
            if after:
                k, prev = after, ">"
                continue
            prev, k = t, k + 1
        return k

    def _generic_call(self, k, prev):
        """The index after the type arguments of a call at k (`f<A, B>(`,
        `new Map<K, V>()`), on one line; else None."""
        if self.tok(k) != "<" or not is_name(prev or ""):
            return None
        _, after = self._angles(k)
        if after > k and self.tok(after) in ("(", "`") and \
                "\n" not in self._code[self._toks[k][1]:self._toks[after][1]]:
            return after
        return None

    def _variables(self, j, base):
        k, out = j + 1, []

        def next_declarator(m):
            if self.tok(m) != ",":
                return False
            nxt, after = self.tok(m + 1), self.tok(m + 2)
            return nxt in ("{", "[") or (is_name(nxt) and after in ("=", ":", ",", ";", "!", ""))

        while k < len(self._toks):
            first = k
            if self.tok(k) in ("{", "["):
                close = self._match[k]
                names = [self.tok(m) for m in range(k + 1, close) if is_name(self.tok(m))
                         and self.tok(m + 1) in (",", "}", "]", "=") and self.tok(m - 1) not in ("=",)]
                k = close + 1
            elif is_name(self.tok(k)):
                names = [self.tok(k)]
                k += 1
            else:
                break
            if self.tok(k) == "!":
                k += 1
            typ, sig = None, None
            if self.tok(k) == ":":
                typ, k = self._type(k + 1, stops=("=", ",", ";"), newline=True)
            if self.tok(k) == "=":
                sig = self._arrow(k + 1)
                k = self._expr_end(k + 1, next_declarator)
            for name in names:
                out.append(dict(base, kind="variable", name=name, type=typ, sigs=[sig] if sig else [],
                                line=self.line(first) if out else base["line"], end=self.line(max(k - 1, first))))
            if next_declarator(k):
                k += 1
                continue
            break
        return out, k + 1 if self.tok(k) == ";" else max(k, j + 1)

    # Class and interface members ---------------------------------------------

    def _member_end(self, k, close):
        prev = None
        while k < close:
            t = self.tok(k)
            if t in (";", ","):
                return k + 1
            if prev is not None and self.newline_before(k) and complete(prev) and t not in EXPR_GOES_ON:
                return k
            if t in OPEN:
                k = self.end(k)
                prev = ")"
                continue
            after = self._generic_call(k, prev)
            if after:
                k, prev = after, ">"
                continue
            prev, k = t, k + 1
        return k

    def _members(self, k, close, kind):
        members = {}
        while k < close:
            t = self.tok(k)
            if t in (";", ","):
                k += 1
                continue
            start = k
            while self.tok(k) == "@":
                k += 1
                while is_name(self.tok(k)) or self.tok(k) == ".":
                    k += 1
                if self.tok(k) == "(":
                    k = self.end(k)
            mods, accessor = [], None
            while True:
                t, nxt = self.tok(k), self.tok(k + 1)
                if nxt in ("(", ":", "?", "=", ";", ",", "}", "<", "!"):
                    break
                if t in MODIFIERS:
                    mods.append(t)
                elif t in ("get", "set") and accessor is None:
                    accessor = t
                else:
                    break
                k += 1
            t = self.tok(k)
            if t == "{" and "static" in mods:
                k = self.end(k)
                continue
            if t == "*":
                k += 1
                t = self.tok(k)
            line, internal = self.line(start), self.internal(start)
            vis = next((m for m in mods if m in VISIBILITY), "public")
            if t.startswith("#"):
                vis, name, k = "private", t, k + 1
            elif t == "(" or t == "<":
                name = "()"
            elif t == "new" and self.tok(k + 1) in ("(", "<"):
                name, k = "new()", k + 1
            elif t == "[":
                group = self.texts(k + 1, self._match[k])
                index = len(group) >= 3 and is_name(group[0]) and group[1] == ":"
                name = "[index]" if index and self.tok(self._match[k] + 1) == ":" else "[%s]" % norm(group)
                if index and self.tok(self._match[k] + 1) == ":":
                    typ, end = self._type(self._match[k] + 2, stops=(";", ","), newline=True)
                    members[name] = {"name": name, "kind": "property", "visibility": vis, "static": False,
                                     "readonly": "readonly" in mods, "optional": False, "type": "[%s]:%s" % (
                                         norm(group), typ), "internal": internal, "line": line, "end": line,
                                     "abstract": False}
                    k = end + 1 if self.tok(end) in (";", ",") else end
                    continue
                k = self.end(k)
            elif is_name(t) or is_string(t) or (t[:1].isdigit()):
                name, k = self.string_value(t), k + 1
            else:
                k = self._member_end(k + 1, close)
                continue
            optional = self.tok(k) == "?"
            k += 1 if optional else 0
            if self.tok(k) == "!":
                k += 1
            member = {"name": name, "visibility": vis, "static": "static" in mods, "readonly": "readonly" in mods,
                      "abstract": "abstract" in mods or kind == "interface", "optional": optional,
                      "internal": internal, "line": line}
            if self.tok(k) in ("(", "<"):
                sig, k = self._signature(k, body=kind == "class")
                if sig is None:
                    k = self._member_end(k, close)
                    continue
                if accessor:
                    typ = sig["returns"] if accessor == "get" else (sig["params"][0]["type"] if sig["params"] else None)
                    old = members.get(name)
                    if old and old.get("kind") == "property":
                        old["readonly"] = False
                        old["type"] = old["type"] or typ
                    else:
                        members[name] = dict(member, kind="property", type=typ, readonly=accessor == "get",
                                             abstract=False, end=line)
                    if self.tok(k) == "{":
                        members[name]["end"] = self.line(self._match[k])
                        k = self.end(k)
                    continue
                sig["body"] = self.tok(k) == "{"
                end_line = self.line(self._match[k]) if sig["body"] else line
                if sig["body"]:
                    k = self.end(k)
                old = members.get(name)
                if old and old.get("kind") == "method":
                    old["sigs"].append(sig)
                    old["end"] = end_line
                else:
                    members[name] = dict(member, kind="method", sigs=[sig], end=end_line)
                if name == "constructor":
                    for p in sig["params"]:
                        if p["promoted"]:
                            members.setdefault(p["name"], {
                                "name": p["name"], "kind": "property", "visibility": p["promoted"], "static": False,
                                "readonly": False, "abstract": False, "optional": p["optional"], "type": p["type"],
                                "internal": internal, "line": line, "end": line})
                continue
            typ, sig = None, None
            if self.tok(k) == ":":
                typ, k = self._type(k + 1, stops=(";", ",", "="), newline=True)
            if self.tok(k) == "=":
                sig = self._arrow(k + 1)
                end = self._member_end(k, close)
            else:
                end = k + 1 if self.tok(k) in (";", ",") else max(k, start + 1)
            members[name] = dict(member, kind="method" if sig and not typ else "property", type=typ,
                                 sigs=[sig] if sig else [], end=self.line(max(end - 1, start)))
            k = end
        return members


def parse(text, path):
    """The declarations of a TypeScript or JavaScript file's text; raises
    ParseError."""
    return Unit(text, path)


# --- The public API diff ---------------------------------------------------------

def visible(decl, member=None):
    if decl.get("internal"):
        return False
    if member is None:
        return True
    return not member.get("internal") and member["visibility"] in ("public", "protected")


def category(d):
    k = d["kind"]
    if k == "function" or (k == "variable" and d.get("sigs")):
        return "function"
    return {"class": "class", "interface": "type", "type": "type", "enum": "enum", "namespace": "namespace",
            "reexport": "re-export"}.get(k, "value")


WORDS = {"function": "a function", "class": "a class", "type": "a type", "enum": "an enum", "namespace": "a namespace",
         "re-export": "a re-export", "value": "a value"}


def change(kind, reason, line, symbol, what, text):
    return {"kind": kind, "reason": reason, "line": line, "symbol": symbol, "change": what, "text": text}


def renamed(gone, new):
    """The one new name beside the one gone, or None."""
    return new[0] if len(gone) == 1 and len(new) == 1 else None


def api_sigs(sigs):
    """The signatures callers see: the overloads, when a function has
    bodiless ones beside its implementation."""
    sigs = [s for s in sigs if s]
    declared = [s for s in sigs if not s.get("body")]
    return declared if declared and len(declared) < len(sigs) else sigs


def sig_text(sig):
    params = ", ".join("%s%s%s%s" % ("..." if p["rest"] else "", p["name"], "?" if p["optional"] else "",
                                     ": " + p["type"] if p["type"] else "") for p in sig["params"])
    return "%s(%s)%s" % ("<%s>" % sig["tparams"] if sig["tparams"] else "", params,
                         ": " + sig["returns"] if sig["returns"] else "")


def sig_diff(before, after):
    """[difference] between two signatures, in words. A parameter renamed is
    none: TypeScript has no named arguments."""
    out = []
    if before["tparams"] != after["tparams"]:
        out.append("type parameters <%s> -> <%s>" % (before["tparams"] or "", after["tparams"] or ""))
    bp, hp = before["params"], after["params"]
    for n, p in enumerate(bp):
        if n >= len(hp):
            out.append("%sparameter `%s` removed" % ("rest " if p["rest"] else "", p["name"]))
            continue
        q = hp[n]
        if p["rest"] and not q["rest"]:
            out.append("`%s` is no longer a rest parameter" % q["name"])
        if p["type"] != q["type"]:
            out.append("type of `%s` %s -> %s" % (q["name"], p["type"] or "none", q["type"] or "none"))
        if p["optional"] and not q["optional"] and not q["rest"]:
            out.append("`%s` became required: calls that omit it break" % q["name"])
    for q in hp[len(bp):]:
        if not q["optional"] and not q["rest"]:
            out.append("new required parameter `%s`" % q["name"])
    if before["returns"] != after["returns"]:
        out.append("return type %s -> %s" % (before["returns"] or "none", after["returns"] or "none"))
    return out


def sigs_diff(before, after):
    b, h = api_sigs(before), api_sigs(after)
    if len(b) == 1 and len(h) == 1:
        return sig_diff(b[0], h[0])
    if not b or not h:
        return []
    texts = [sig_text(s) for s in h]
    return ["overload `%s` removed or changed" % sig_text(s) for s in b if sig_text(s) not in texts]


def api_changes(base, head):
    """[change] between the base and head Units of one file (either may be
    None): what consumers outside the diff can break on. Each change has
    `kind`, `reason`, `line` (in the head, or None), `symbol`, `change`
    (`removed` or `signature`) and `text`, the declaration's line."""
    out = []
    b_exp = {k: d for k, d in (base.exports.items() if base else []) if visible(d)}
    h_exp = head.exports if head else {}
    gone = [k for k in b_exp if k not in h_exp]
    new = [k for k, d in h_exp.items() if k not in (base.exports if base else {}) and visible(d)]
    for k in gone:
        d, to = b_exp[k], renamed(gone, new)
        reason = "export `%s` (%s) removed" % (k, WORDS[category(d)])
        line, text = None, base.text(d["line"])
        if to:
            reason += "; `%s` appears in its place, a rename" % to
            line, text = h_exp[to]["line"], head.text(h_exp[to]["line"])
        out.append(change("export-removed", reason, line, k, "removed", text))
    for k, b in b_exp.items():
        h = h_exp.get(k)
        if h is not None:
            out += decl_changes(base, head, k, b, h)
    kept = [s for s, _ in (head.stars if head else [])]
    for spec, line in (base.stars if base else []):
        if spec not in kept:
            out.append(change("reexport-removed", "`export * from '%s'` removed: what it re-exported is gone from"
                              " this module" % spec, None, "*", "removed", base.text(line)))
    return out


def decl_changes(base, head, name, b, h):
    cb, ch = category(b), category(h)
    text, line = head.text(h["line"]), h["line"]
    if cb != ch:
        return [change("export-changed", "export `%s` was %s, now %s" % (name, WORDS[cb], WORDS[ch]), line, name,
                       "signature", text)]
    if cb == "function":
        diff = sigs_diff(b.get("sigs") or [], h.get("sigs") or [])
        return [change("signature-changed", "function `%s()`: %s" % (name, "; ".join(diff)), line, name,
                       "signature", text)] if diff else []
    if cb == "class":
        return class_changes(base, head, name, b, h)
    if b["kind"] == h["kind"] == "interface":
        return interface_changes(head, name, b, h)
    if b["kind"] == h["kind"] == "type":
        diff = []
        if b["tparams"] != h["tparams"]:
            diff.append("type parameters <%s> -> <%s>" % (b["tparams"] or "", h["tparams"] or ""))
        if b["text"] != h["text"]:
            diff.append("%s -> %s" % (b["text"], h["text"]))
        return [change("type-changed", "type `%s`: %s" % (name, "; ".join(diff)), line, name, "signature",
                       text)] if diff else []
    if cb == "enum":
        return enum_changes(base, head, name, b, h)
    if cb == "value" and b.get("type") != h.get("type") and b.get("kind") == h.get("kind") == "variable":
        return [change("type-changed", "`%s`: type %s -> %s" % (name, b["type"] or "none", h["type"] or "none"), line,
                       name, "signature", text)]
    return []


def member_label(m):
    return "method" if m["kind"] == "method" else "property"


def member_changes(head, owner, b, h, word):
    """[change] of one member kept by a class or an interface."""
    where = "%s.%s" % (owner, b["name"])
    shown = "`%s()`" % where if b["kind"] == "method" else "`%s`" % where
    if b["kind"] != h["kind"] and not (b.get("sigs") and h.get("sigs")):
        return [change("property-changed", "%s %s became a %s" % (word, shown, member_label(h)), h["line"], where,
                       "signature", head.text(h["line"]))]
    diff = []
    if b["static"] != h["static"]:
        diff.append("became static" if h["static"] else "no longer static")
    if b.get("sigs") and h.get("sigs"):
        diff += sigs_diff(b["sigs"], h["sigs"])
    else:
        if b.get("type") != h.get("type"):
            diff.append("type %s -> %s" % (b.get("type") or "none", h.get("type") or "none"))
        if h["readonly"] and not b["readonly"]:
            diff.append("became readonly: writes outside the diff break")
    if b["optional"] and not h["optional"]:
        diff.append("became required: objects outside the diff must provide it")
    if not diff:
        return []
    kind = "signature-changed" if b["kind"] == "method" else "property-changed"
    return [change(kind, "%s %s: %s" % (word, shown, "; ".join(diff)), h["line"], where, "signature",
                   head.text(h["line"]))]


def heritage_changes(head, name, b, h, label):
    out = []
    for rel in ("extends", "implements"):
        lost = [x for x in b.get(rel) or [] if x not in (h.get(rel) or [])]
        if lost:
            out.append(change("class-changed", "%s `%s` no longer %s %s: type checks on it break" % (
                label, name, rel, ", ".join("`%s`" % x for x in lost)), h["line"], name, "signature",
                head.text(h["line"])))
    return out


def class_changes(base, head, name, b, h):
    out = []
    if h["abstract"] and not b["abstract"]:
        out.append(change("class-changed", "class `%s` became abstract: `new %s()` breaks" % (name, name), h["line"],
                          name, "signature", head.text(h["line"])))
    out += heritage_changes(head, name, b, h, "class")
    b_m = {k: m for k, m in b["members"].items() if visible(b, m)}
    h_m = h["members"]
    for kind in ("method", "property"):
        gone = [k for k, m in b_m.items() if k not in h_m and member_label(m) == kind]
        new = [k for k, m in h_m.items() if k not in b["members"] and visible(h, m) and member_label(m) == kind]
        for k in gone:
            m, to = b_m[k], renamed(gone, new)
            where = "%s.%s" % (name, m["name"])
            shown = "`%s()`" % where if kind == "method" else "`%s`" % where
            reason = "%s %s %s removed" % (m["visibility"], kind, shown)
            line, text = h["line"], base.text(m["line"])
            if to:
                n = h_m[to]
                reason += "; `%s.%s%s` appears in its place, a rename" % (name, n["name"], "()" if kind == "method"
                                                                          else "")
                line, text = n["line"], head.text(n["line"])
            label = "method-removed" if kind == "method" else "property-removed"
            if m["name"] == "constructor":
                reason = "the constructor of `%s` was removed" % name
            out.append(change(label, reason, line, where, "removed", text))
    for k, m in b_m.items():
        n = h_m.get(k)
        if n is None:
            continue
        where = "%s.%s" % (name, m["name"])
        if not visible(h, n):
            out.append(change("visibility-reduced", "%s `%s` %s -> %s" % (member_label(m), where, m["visibility"],
                                                                         n["visibility"] if not n.get("internal")
                                                                         else "@internal"),
                              n["line"], where, "removed", head.text(n["line"])))
            continue
        word = "constructor of" if m["name"] == "constructor" else "%s %s" % (n["visibility"], member_label(n))
        if m["name"] == "constructor":
            diff = sigs_diff(m.get("sigs") or [], n.get("sigs") or [])
            if diff:
                out.append(change("signature-changed", "the constructor of `%s`: %s" % (name, "; ".join(diff)),
                                  n["line"], where, "signature", head.text(n["line"])))
            continue
        out += member_changes(head, name, m, n, word)
    for k, n in h_m.items():
        if k not in b["members"] and n["abstract"] and visible(h, n):
            out.append(change("abstract-member-added", "abstract %s `%s.%s` added: subclasses outside the diff must"
                              " define it" % (member_label(n), name, n["name"]), n["line"], "%s.%s" % (name, n["name"]),
                              "signature", head.text(n["line"])))
    return out


def interface_changes(head, name, b, h):
    out = heritage_changes(head, name, b, h, "interface")
    b_m = {k: m for k, m in b["members"].items() if not m.get("internal")}
    h_m = h["members"]
    gone = [k for k in b_m if k not in h_m]
    new = [k for k, m in h_m.items() if k not in b["members"]]
    for k in gone:
        m, to = b_m[k], renamed(gone, new)
        reason = "member `%s.%s` removed" % (name, m["name"])
        line, text = h["line"], None
        if to:
            reason += "; `%s.%s` appears in its place, a rename" % (name, h_m[to]["name"])
            line, text = h_m[to]["line"], head.text(h_m[to]["line"])
        out.append(change("member-removed", reason, line, "%s.%s" % (name, m["name"]), "removed", text))
    for k, m in b_m.items():
        if k in h_m:
            out += [dict(c, kind="member-changed" if c["kind"] == "property-changed" else c["kind"])
                    for c in member_changes(head, name, m, h_m[k], "member")]
    for k in new:
        n = h_m[k]
        if not n["optional"] and k not in ("()", "new()") and not k.startswith("["):
            out.append(change("interface-member-added", "required member `%s.%s` added: implementations and object"
                              " literals outside the diff must provide it" % (name, n["name"]), n["line"],
                              "%s.%s" % (name, n["name"]), "signature", head.text(n["line"])))
    return out


def enum_changes(base, head, name, b, h):
    out = []
    for k, m in b["members"].items():
        n = h["members"].get(k)
        where = "%s.%s" % (name, k)
        if n is None:
            out.append(change("enum-member-removed", "member `%s` removed" % where, h["line"], where, "removed",
                              base.text(m["line"])))
        elif m["value"] is not None and n["value"] is not None and m["value"] != n["value"]:
            out.append(change("enum-member-changed", "member `%s` value %s -> %s: stored or sent values change"
                              " meaning" % (where, m["value"], n["value"]), n["line"], where, "signature",
                              head.text(n["line"])))
    return out


# --- Fan-in -----------------------------------------------------------------------

def symbols(base, head, changed_lines):
    """[{symbol, change, line}]: the exports and public members a file's
    diff removes, changes or edits the body of (one the base already had: a
    new one has no caller to count). `changed_lines` are the head lines its
    hunks touch."""
    out, seen = [], set()
    for ch in api_changes(base, head):
        if ch["symbol"] not in seen and ch["symbol"] != "*":
            seen.add(ch["symbol"])
            out.append({"symbol": ch["symbol"], "change": ch["change"], "line": ch["line"]})
    if head is None or base is None:
        return out
    lines = sorted(set(changed_lines))

    def touched(start, end):
        k = bisect.bisect_left(lines, start)
        return k < len(lines) and lines[k] <= (end or start)

    for k, d in head.exports.items():
        b = base.exports.get(k)
        if not visible(d) or b is None or d["kind"] in ("reexport", "value"):
            continue
        if d["kind"] == "class" and b["kind"] == "class":
            for mk, m in d["members"].items():
                name = "%s.%s" % (k, m["name"])
                if m["kind"] == "method" and visible(d, m) and mk in b["members"] and name not in seen \
                        and touched(m["line"], m.get("end")):
                    seen.add(name)
                    out.append({"symbol": name, "change": "body", "line": m["line"]})
        elif category(d) == "function" and k not in seen and touched(d["line"], d.get("end")):
            seen.add(k)
            out.append({"symbol": k, "change": "body", "line": d["line"]})
    return out


def reference(symbol):
    """(word the line must hold, pattern of a reference) for a symbol of
    `symbols`: `Class.member` matches `.member`, `Class.constructor`
    matches `new Class(` and `extends Class`, a bare export matches its
    name as a word that is not a property (`.name`)."""
    owner, sep, member = symbol.partition(".")
    if not sep:
        return owner, re.compile(r"(?<![\w$.#])%s(?![\w$])" % re.escape(owner))
    if member == "constructor":
        name = re.escape(owner)
        return owner, re.compile(r"\bnew\s+%s\s*[<(]|\bextends\s+%s\b" % (name, name))
    return member, re.compile(r"(?:\?\.|\.)\s*%s(?![\w$])" % re.escape(member))


def member_name(symbol):
    """The name a fan-in count stands on: the member of `Class.member`, the
    class for its constructor."""
    owner, _, member = symbol.partition(".")
    return owner if member == "constructor" else member or symbol


# --- The import graph ---------------------------------------------------------------

def quick_imports(text, path):
    """[(kind, specifier, line)] of a file the diff does not touch: its
    imports, re-exports, `require` and `import()` calls, without parsing
    its declarations. None when it can't be read."""
    try:
        code, _, strings = strip(text, jsx_allowed(path))
    except ParseError:
        return None
    toks = [(m.group(0), m.start()) for m in TOKEN.finditer(code)]
    starts = [0] + [m.end() for m in re.finditer(r"\n", code)]
    out = []

    def value(i):
        if i < len(toks) and is_string(toks[i][0]):
            return strings.get(toks[i][1])
        return None

    for i, (t, off) in enumerate(toks):
        prev = toks[i - 1][0] if i else ""
        if prev in (".", "?."):
            continue
        spec, kind = None, None
        if t == "from" and value(i + 1) is not None:
            spec, kind = value(i + 1), "value"
        elif t in ("import", "require") and i + 2 < len(toks) and toks[i + 1][0] == "(":
            spec, kind = value(i + 2), "dynamic"
        elif t == "import" and value(i + 1) is not None:
            spec, kind = value(i + 1), "side-effect"
        if spec is not None:
            out.append((kind, spec, bisect.bisect_right(starts, off)))
    return out


SOURCE_ROOTS = ("src", "lib", "app", "source")
RESOLVE_EXTS = (".ts", ".tsx", ".d.ts", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
JS_TO_TS = {".js": (".ts", ".tsx", ".d.ts"), ".jsx": (".tsx",), ".mjs": (".mts", ".d.mts"), ".cjs": (".cts", ".d.cts")}
CONFIGS = ("tsconfig.json", "jsconfig.json")
OUTPUT_DIR = re.compile(r"^(?:\./)?(?:dist|build|lib|out|esm|cjs|types)/")


def jsonc(text):
    """The value of a JSON text with comments and trailing commas, None
    when it can't be read."""
    if text is None:
        return None
    pieces = []
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"|//[^\n]*|/\*.*?\*/|[^"/]+|/', text, re.S):
        s = m.group()
        pieces.append("" if s.startswith(("//", "/*")) else s)
    text = "".join(pieces)
    text = re.sub(r'("(?:[^"\\]|\\.)*")|,(\s*[}\]])', lambda m: m.group(1) or m.group(2), text)
    try:
        return json.loads(text)
    except ValueError:
        return None


def join(*parts):
    return posixpath.normpath(posixpath.join(*[p for p in parts if p])) if any(parts) else ""


class Project:
    """Which file an import resolves to, and which module a file belongs
    to. A module is the first directory under a source root (`src/`,
    `lib/`, `app/`, `source/`) of a package (a directory with a
    `package.json`), else the package's own first directory; a file right
    under a source root, or a package, belongs to it; `/` is the root."""

    def __init__(self, files, read):
        """`files`: the paths of the head tree; `read(path)`: its text, or
        None."""
        self.packages, self.names, self.configs = {}, {}, {}
        for path in sorted(files):
            base = posixpath.basename(path)
            d = posixpath.dirname(path)
            if base == "package.json":
                data = jsonc(read(path))
                data = data if isinstance(data, dict) else {}
                self.packages[d] = data
                if d and isinstance(data.get("name"), str) and data["name"]:
                    self.names.setdefault(data["name"], d)
            elif base in CONFIGS and (d not in self.configs or base == "tsconfig.json"):
                self.configs[d] = self._config(path, read, 0)
        self.rule = ("the first directory under a source root (%s) of each package (a directory with a"
                     " package.json), else its first directory; `/` is the root" % ", ".join(
                         "`%s/`" % r for r in SOURCE_ROOTS))
        if self.names:
            self.rule += "; workspace packages %s" % ", ".join("`%s`" % n for n in sorted(self.names))
        aliases = sorted({p for c in self.configs.values() for p, _ in c["paths"]})
        if aliases:
            self.rule += "; path aliases %s" % ", ".join("`%s`" % a for a in aliases)

    def _config(self, path, read, depth):
        here = posixpath.dirname(path)
        data = jsonc(read(path))
        data = data if isinstance(data, dict) else {}
        out = {"paths": [], "baseurl": None, "base": here}
        ext = data.get("extends")
        for e in ([ext] if isinstance(ext, str) else ext if isinstance(ext, list) else []):
            if isinstance(e, str) and e.startswith(".") and depth < 5:
                p = join(here, e)
                parent = self._config(p if p.endswith(".json") else p + ".json", read, depth + 1)
                out = {"paths": parent["paths"] or out["paths"], "baseurl": parent["baseurl"] or out["baseurl"],
                       "base": parent["base"] if parent["paths"] else out["base"]}
        co = data.get("compilerOptions") if isinstance(data.get("compilerOptions"), dict) else {}
        if isinstance(co.get("baseUrl"), str):
            out["baseurl"] = join(here, co["baseUrl"]) or "."
        if isinstance(co.get("paths"), dict):
            out["paths"] = [(k, [t for t in v if isinstance(t, str)]) for k, v in co["paths"].items()
                            if isinstance(v, list)]
            out["base"] = here
        if out["baseurl"] is not None and out["paths"]:
            out["base"] = out["baseurl"]
        return out

    def config_for(self, path):
        d = posixpath.dirname(path)
        while True:
            if d in self.configs:
                return self.configs[d]
            if not d:
                return None
            d = posixpath.dirname(d)

    def package_of(self, path):
        best = ""
        for d in self.packages:
            if d and path.startswith(d + "/") and len(d) > len(best):
                best = d
        return best

    def module_of(self, path):
        pkg = self.package_of(path)
        parts = (path[len(pkg) + 1:] if pkg else path).split("/")
        root = pkg
        if len(parts) > 1 and parts[0] in SOURCE_ROOTS:
            root, parts = join(pkg, parts[0]), parts[1:]
        if len(parts) > 1:
            return join(root, parts[0])
        return root or "/"

    @staticmethod
    def probe(p, exists):
        if p in ("", ".") or p.startswith("../") or p == "..":
            p = "" if p in ("", ".") else None
        if p is None:
            return None
        cands = [p] if p else []
        root, ext = posixpath.splitext(p)
        cands += [root + e for e in JS_TO_TS.get(ext, ())]
        if p.endswith(".d.ts"):
            cands.append(p[:-len(".d.ts")] + ".ts")
        cands += [p + e for e in RESOLVE_EXTS] + [join(p, "index") + e for e in RESOLVE_EXTS]
        return next((c for c in cands if exists(c)), None)

    def entry(self, d, exists):
        data = self.packages.get(d) or {}
        found = []
        exp = data.get("exports")
        if isinstance(exp, dict):
            exp = exp.get(".", exp if not any(k.startswith(".") for k in exp) else None)
        while isinstance(exp, dict):
            exp = next((exp[k] for k in ("types", "import", "default", "require", "node") if k in exp), None)
        if isinstance(exp, str):
            found.append(exp)
        found += [data[k] for k in ("source", "types", "typings", "module", "main") if isinstance(data.get(k), str)]
        for f in found:
            r = self.probe(join(d, f), exists) or (OUTPUT_DIR.match(f) and self.probe(
                join(d, OUTPUT_DIR.sub("src/", f)), exists))
            if r:
                return r
        return self.probe(join(d, "src", "index"), exists) or self.probe(join(d, "index"), exists)

    def resolve(self, importer, spec, exists):
        """The repository file `spec` imported from `importer` resolves to,
        on the side `exists` describes; None outside the repository."""
        if spec.startswith(("./", "../")) or spec in (".", ".."):
            return self.probe(join(posixpath.dirname(importer), spec), exists)
        if spec.startswith("/") or ":" in spec.split("/", 1)[0]:
            return None
        conf = self.config_for(importer)
        if conf:
            # TypeScript tries an exact pattern, then the longest prefix.
            for pattern, targets in sorted(conf["paths"], key=lambda p: ("*" in p[0], -len(p[0].split("*")[0]))):
                head, star, tail = pattern.partition("*")
                if star:
                    if not (spec.startswith(head) and spec.endswith(tail) and len(spec) >= len(head) + len(tail)):
                        continue
                    middle = spec[len(head):len(spec) - len(tail)]
                elif spec != pattern:
                    continue
                else:
                    middle = ""
                for target in targets:
                    r = self.probe(join(conf["base"], target.replace("*", middle, 1)), exists)
                    if r:
                        return r
            if conf["baseurl"] is not None:
                r = self.probe(join(conf["baseurl"], spec), exists)
                if r:
                    return r
        for name, d in sorted(self.names.items(), key=lambda kv: -len(kv[0])):
            if spec == name:
                return self.entry(d, exists)
            if spec.startswith(name + "/"):
                sub = spec[len(name) + 1:]
                return self.probe(join(d, sub), exists) or self.probe(join(d, "src", sub), exists)
        return None
