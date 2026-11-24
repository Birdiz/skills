"""The PHP adapter: what the review reads in PHP code without running PHP.

- `parse`: the declarations of one PHP file (namespace, `use` imports,
  classes, interfaces, traits and enums with their methods, constants,
  cases and properties, functions), from a lexer that blanks comments,
  strings and attributes. A file without a `<?php` tag (a template), or
  one the lexer can't finish, raises `ParseError`: the detectors then say
  they could not cover it.
- `api_changes`: the signature-level diff of the public API between a
  file's base and head, labelled heuristic by its detector. Visible means
  public, or protected in a class that is not final; a class or member
  marked `@internal` is left out, as Roave's BC check does.
- `symbols`: the public symbols the diff removes or changes, for fan-in,
  each with the pattern its references match.
- `Modules` and `quick_imports`: the import graph's nodes. A module is the
  namespace segment under a PSR-4 prefix of `composer.json` (`App\\Billing`
  under `App\\`), else the first two namespace segments.

Roave's `roave/backward-compatibility-check` is not run: it runs `composer
install` in its own clones of the repository (see `detectors.ADAPTERS`).
"""
import bisect
import json
import re

OPEN_TAG = re.compile(r"<\?php\b|<\?=", re.I)
SPECIAL = re.compile(r"//|#\[|#|/\*|'|\"|`|<<<|\?>|\[|\]")
STRINGS = {"'": re.compile(r"'(?:[^'\\]|\\.)*'", re.S), '"': re.compile(r'"(?:[^"\\]|\\.)*"', re.S),
           "`": re.compile(r"`(?:[^`\\]|\\.)*`", re.S)}
HEREDOC = re.compile(r"<<<[ \t]*(['\"]?)([A-Za-z_]\w*)\1\r?\n")
TOKEN = re.compile(r"\$[A-Za-z_]\w*|\\?[A-Za-z_]\w*(?:\\[A-Za-z_]\w*)*\\?|\d[\w.]*|\.\.\.|\?->|->|::|=>|\S")
NAME = re.compile(r"^\\?[A-Za-z_]\w*(?:\\[A-Za-z_]\w*)*$")
CLASS_KINDS = ("class", "interface", "trait", "enum")
CLASS_MODIFIERS = ("abstract", "final", "readonly")
MEMBER_MODIFIERS = ("public", "protected", "private", "static", "abstract", "final", "readonly", "var")
BUILTIN = {"int", "integer", "float", "double", "string", "bool", "boolean", "array", "callable", "iterable",
           "object", "mixed", "void", "never", "null", "false", "true", "self", "static", "parent", "resource"}
INTERNAL = re.compile(r"@internal\b")


class ParseError(Exception):
    pass


def is_code(path):
    """A PHP code file, not a template."""
    low = path.lower()
    return low.endswith(".php") and not low.endswith((".blade.php", ".twig.php", ".tpl.php"))


# --- Lexing -------------------------------------------------------------------

def blank(text):
    return re.sub(r"[^\n]", " ", text)


def strip(text):
    """(code, docblocks): the text with inline HTML, comments, string
    contents and attributes blanked, newlines and offsets kept; docblocks as
    [(end offset, text)]."""
    m = OPEN_TAG.search(text)
    if not m:
        raise ParseError("no `<?php` tag: a template, not code")
    out, docs = [blank(text[:m.end()])], []
    i, n, attr = m.end(), len(text), 0
    while i < n:
        m = SPECIAL.search(text, i)
        if not m:
            out.append(blank(text[i:]) if attr else text[i:])
            break
        seg = text[i:m.start()]
        out.append(blank(seg) if attr else seg)
        tok, i = m.group(0), m.start()
        if tok in ("[", "]"):
            if attr:
                attr += 1 if tok == "[" else -1
                out.append(" ")
            else:
                out.append(tok)
            i += 1
        elif tok == "#[":
            attr += 1
            out.append("  ")
            i += 2
        elif tok in ("//", "#"):
            j = text.find("\n", i)
            j = n if j < 0 else j
            k = text.find("?>", i, j)
            j = k if k >= 0 else j
            out.append(blank(text[i:j]))
            i = j
        elif tok == "/*":
            j = text.find("*/", i + 2)
            if j < 0:
                raise ParseError("a comment never closes (line %d)" % (text.count("\n", 0, i) + 1))
            j += 2
            if text.startswith("/**", i):
                docs.append((j, text[i:j]))
            out.append(blank(text[i:j]))
            i = j
        elif tok in STRINGS:
            sm = STRINGS[tok].match(text, i)
            if not sm:
                raise ParseError("a string never closes (line %d)" % (text.count("\n", 0, i) + 1))
            piece = tok + blank(text[i + 1:sm.end() - 1]) + tok
            out.append(blank(piece) if attr else piece)
            i = sm.end()
        elif tok == "<<<":
            hm = HEREDOC.match(text, i)
            if not hm:
                out.append(blank(tok) if attr else tok)
                i += 3
                continue
            end = re.compile(r"^[ \t]*%s\b" % re.escape(hm.group(2)), re.M).search(text, hm.end())
            if not end:
                raise ParseError("a heredoc never closes (line %d)" % (text.count("\n", 0, i) + 1))
            out.append("''" + blank(text[i + 2:end.end()]))
            i = end.end()
        else:  # `?>`: inline HTML until the next open tag
            nxt = OPEN_TAG.search(text, i + 2)
            j = nxt.end() if nxt else n
            out.append(";" + blank(text[i + 1:j]))
            i = j
    if attr:
        raise ParseError("an attribute never closes")
    return "".join(out), docs


# --- Parsing ------------------------------------------------------------------

class Unit:
    """The declarations of one PHP file."""

    def __init__(self, text):
        self.lines = text.split("\n")
        self.namespaces = []
        self.imports = []  # (kind, fqcn, line)
        self.classes = {}  # fqcn -> class
        self.functions = {}  # lower fqcn -> function
        self._parse(text)

    def text(self, line):
        return self.lines[line - 1] if line and 0 < line <= len(self.lines) else ""

    # The token stream -----------------------------------------------------

    def _parse(self, text):
        code, docs = strip(text)
        self._starts = [0] + [m.end() for m in re.finditer(r"\n", code)]
        self._code, self._docs = code, docs
        self._doc_ends = [d[0] for d in docs]
        toks = [(m.group(0), m.start()) for m in TOKEN.finditer(code)]
        self._toks = toks
        self.ns, self.uses = "", {"class": {}, "function": {}, "const": {}}
        stack, i = [], 0
        while i < len(toks):
            t, off = toks[i]
            low = t.lower()
            scope = stack[-1][0] if stack else "top"
            if t == "{":
                stack.append(("other", None))
                i += 1
            elif t == "}":
                if not stack:
                    raise ParseError("a `}` closes nothing (line %d)" % self.line(off))
                kind, data = stack.pop()
                if kind in ("class", "function") and data is not None:
                    data["end"] = self.line(off)
                elif kind == "namespace":
                    self._namespace("")
                i += 1
            elif scope in ("top", "namespace"):
                i = self._top(i, low, stack)
            elif scope == "class":
                i = self._member(i, stack)
            else:
                i += 1
        if stack:
            raise ParseError("a `{` never closes")

    def line(self, off):
        return bisect.bisect_right(self._starts, off)

    def tok(self, i):
        return self._toks[i][0] if i < len(self._toks) else ""

    def _namespace(self, name):
        self.ns = name.lstrip("\\")
        self.uses = {"class": {}, "function": {}, "const": {}}
        if self.ns and self.ns not in self.namespaces:
            self.namespaces.append(self.ns)

    def internal(self, i):
        """Whether a docblock right before token i says `@internal`."""
        off = self._toks[i][1]
        k = bisect.bisect_right(self._doc_ends, off) - 1
        if k < 0:
            return False
        end, doc = self._docs[k]
        return not self._code[end:off].strip() and bool(INTERNAL.search(doc))

    def _top(self, i, low, stack):
        prev = self.tok(i - 1) if i else ""
        if low == "namespace" and prev not in ("::", "->", "?->"):
            j, name = i + 1, ""
            if NAME.match(self.tok(j)):
                name, j = self.tok(j), j + 1
            self._namespace(name)
            if self.tok(j) == "{":
                stack.append(("namespace", None))
            return j + 1
        if low == "use" and prev not in ("::", "->", "?->", ")") and self.tok(i + 1) != "(":
            return self._use(i)
        if (low in CLASS_KINDS or low in CLASS_MODIFIERS) and prev not in ("new", "::", "->", "?->"):
            j, mods = i, []
            while self.tok(j).lower() in CLASS_MODIFIERS:
                mods.append(self.tok(j).lower())
                j += 1
            kind = self.tok(j).lower()
            if kind in CLASS_KINDS and NAME.match(self.tok(j + 1)) and "\\" not in self.tok(j + 1) \
                    and self.tok(j + 1).lower() not in ("extends", "implements"):
                return self._class(i, j, kind, mods, stack)
            return i + 1
        if low == "function" and prev not in ("::", "->", "?->"):
            j = i + 1
            if self.tok(j) == "&":
                j += 1
            if NAME.match(self.tok(j)) and self.tok(j + 1) == "(":
                fn = self._signature(j)
                fn.update({"name": self.tok(j), "visibility": "public", "internal": self.internal(i),
                           "line": self.line(self._toks[i][1])})
                fqcn = (self.ns + "\\" + fn["name"]) if self.ns else fn["name"]
                fn["fqcn"] = fqcn
                self.functions.setdefault(fqcn.lower(), fn)
                return self._body(fn, stack)
        return i + 1

    def _use(self, i):
        """Parse `use ...;` at the top or in a namespace; returns the index after it."""
        j, kind = i + 1, "class"
        if self.tok(j).lower() in ("function", "const"):
            kind, j = self.tok(j).lower(), j + 1
        line = self.line(self._toks[i][1])
        while j < len(self._toks) and self.tok(j) != ";":
            name = self.tok(j)
            if name.endswith("\\") and NAME.match(name[:-1]) and self.tok(j + 1) == "{":
                prefix, j = name.lstrip("\\"), j + 2
                while j < len(self._toks) and self.tok(j) not in ("}", ";"):
                    sub_kind = kind
                    if self.tok(j).lower() in ("function", "const") and NAME.match(self.tok(j + 1)):
                        sub_kind, j = self.tok(j).lower(), j + 1
                    if NAME.match(self.tok(j)):
                        j = self._alias(prefix + self.tok(j).lstrip("\\"), j, sub_kind, line)
                    else:
                        j += 1
                continue
            if not NAME.match(name):
                j += 1
                continue
            j = self._alias(name.lstrip("\\"), j, kind, line)
        return j + 1

    def _alias(self, fqcn, j, kind, line):
        alias = fqcn.rsplit("\\", 1)[-1]
        j += 1
        if self.tok(j).lower() == "as" and NAME.match(self.tok(j + 1)):
            alias, j = self.tok(j + 1), j + 2
        self.uses[kind][alias.lower() if kind != "const" else alias] = fqcn
        self.imports.append((kind, fqcn, line))
        return j

    def resolve(self, name):
        """A class name as written, fully qualified."""
        if not name:
            return name
        if name.startswith("\\"):
            return name[1:]
        if name.lower() in BUILTIN:
            return name.lower()
        head, _, rest = name.partition("\\")
        if head.lower() == "namespace":
            return (self.ns + "\\" + rest) if self.ns else rest
        if head.lower() in self.uses["class"]:
            base = self.uses["class"][head.lower()]
            return base + "\\" + rest if rest else base
        return (self.ns + "\\" + name) if self.ns else name

    def type_of(self, toks):
        return "".join(self.resolve(t) if NAME.match(t) else t for t in toks) or None

    def _class(self, i, j, kind, mods, stack):
        name = self.tok(j + 1)
        fqcn = (self.ns + "\\" + name) if self.ns else name
        cls = {"fqcn": fqcn, "name": name, "kind": kind, "abstract": "abstract" in mods or kind == "interface",
               "final": "final" in mods, "readonly": "readonly" in mods, "extends": [], "implements": [],
               "internal": self.internal(i), "line": self.line(self._toks[i][1]), "end": None,
               "methods": {}, "constants": {}, "properties": {}}
        k, into = j + 2, None
        while k < len(self._toks) and self.tok(k) != "{":
            t = self.tok(k).lower()
            if t in ("extends", "implements"):
                into = cls[t]
            elif into is not None and NAME.match(self.tok(k)):
                into.append(self.resolve(self.tok(k)))
            k += 1
        self.classes.setdefault(fqcn, cls)
        stack.append(("class", cls))
        return k + 1

    def _signature(self, j):
        """{params, returns} of the function named at token j, `(` at j + 1,
        and `_after`, the index after its return type."""
        k, depth, params, cur = j + 2, 1, [], []
        while k < len(self._toks):
            t = self.tok(k)
            if t in ("(", "[", "{"):
                depth += 1
            elif t in (")", "]", "}"):
                depth -= 1
                if depth == 0:
                    break
            if t == "," and depth == 1:
                params.append(cur)
                cur = []
            else:
                cur.append(t)
            k += 1
        if cur:
            params.append(cur)
        out = {"params": [p for p in (self._param(x) for x in params) if p], "returns": None}
        k += 1
        if self.tok(k) == ":":
            rt, k = [], k + 1
            while k < len(self._toks) and self.tok(k) not in ("{", ";", "=>"):
                rt.append(self.tok(k))
                k += 1
            out["returns"] = self.type_of(rt)
        out["_after"] = k
        return out

    def _param(self, toks):
        names = [n for n, t in enumerate(toks) if t.startswith("$")]
        if not names:
            return None
        at = names[0]
        before = toks[:at]
        promoted = next((t.lower() for t in before if t.lower() in ("public", "protected", "private")), None)
        if promoted is None and any(t.lower() == "readonly" for t in before):
            promoted = "public"
        before = [t for t in before if t.lower() not in ("public", "protected", "private", "readonly")]
        variadic = "..." in before
        before = [t for t in before if t != "..."]
        byref = bool(before) and before[-1] == "&"
        if byref:
            before = before[:-1]
        return {"name": toks[at], "type": self.type_of(before), "default": "=" in toks[at + 1:],
                "variadic": variadic, "byref": byref, "promoted": promoted}

    def _body(self, fn, stack):
        k = fn.pop("_after")
        if self.tok(k) == "{":
            stack.append(("function", fn))
        else:
            fn["end"] = fn["line"]
        return k + 1

    def _member(self, i, stack):
        cls = stack[-1][1]
        j, mods = i, []
        while self.tok(j).lower() in MEMBER_MODIFIERS:
            mods.append(self.tok(j).lower())
            j += 1
        t = self.tok(j).lower()
        vis = next((m for m in mods if m in ("public", "protected", "private")), "public")
        line = self.line(self._toks[i][1])
        internal = self.internal(i)
        if t == "function":
            k = j + 1
            if self.tok(k) == "&":
                k += 1
            if not NAME.match(self.tok(k)) or self.tok(k + 1) != "(":
                return j + 1
            m = self._signature(k)
            m.update({"name": self.tok(k), "visibility": vis, "static": "static" in mods,
                      "abstract": "abstract" in mods or cls["kind"] == "interface", "final": "final" in mods,
                      "internal": internal, "line": line})
            cls["methods"].setdefault(m["name"].lower(), m)
            if m["name"].lower() == "__construct":
                for p in m["params"]:
                    if p["promoted"]:
                        cls["properties"].setdefault(p["name"][1:], {
                            "name": p["name"][1:], "visibility": p["promoted"], "static": False,
                            "type": p["type"], "readonly": True, "internal": internal, "line": line})
            return self._body(m, stack)
        if t in ("const", "case"):
            k, names, depth, last, seen_eq = j + 1, [], 0, None, False
            while k < len(self._toks) and not (self.tok(k) in (";", "}") and depth == 0):
                tk = self.tok(k)
                if tk in ("(", "["):
                    depth += 1
                elif tk in (")", "]"):
                    depth -= 1
                elif tk == "=" and depth == 0 and not seen_eq:
                    if last:
                        names.append(last)
                    seen_eq = True
                elif tk == "," and depth == 0:
                    seen_eq, last = False, None
                elif NAME.match(tk) and not seen_eq:
                    last = tk
                k += 1
            if t == "case" and last and not seen_eq:
                names.append(last)
            for name in names:
                cls["constants"].setdefault(name, {"name": name, "visibility": vis, "case": t == "case",
                                                   "internal": internal, "line": line})
            return k + 1 if self.tok(k) == ";" else k
        if t == "use":
            k = j + 1
            while k < len(self._toks) and self.tok(k) not in (";", "{"):
                k += 1
            return k + 1 if self.tok(k) == ";" else k
        if mods:
            k, typ = j, []
            while k < len(self._toks) and not self.tok(k).startswith("$") and self.tok(k) not in (";", "{", "}"):
                typ.append(self.tok(k))
                k += 1
            depth, after_eq = 0, False
            while k < len(self._toks):
                tk = self.tok(k)
                if tk in ("(", "["):
                    depth += 1
                elif tk in (")", "]"):
                    depth -= 1
                elif depth == 0 and tk in (";", "{", "}"):
                    break
                elif depth == 0 and tk in (",", "="):
                    after_eq = tk == "="
                elif depth == 0 and tk.startswith("$") and not after_eq:
                    name = tk[1:]
                    cls["properties"].setdefault(name, {
                        "name": name, "visibility": vis, "static": "static" in mods, "type": self.type_of(typ),
                        "readonly": "readonly" in mods or cls["readonly"], "internal": internal, "line": line})
                k += 1
            return k + 1 if self.tok(k) == ";" else k
        return j + 1


def parse(text):
    """The declarations of a PHP file's text; raises ParseError."""
    return Unit(text)


# --- The public API diff ---------------------------------------------------------

def visible(cls, member=None):
    if cls["internal"]:
        return False
    if member is None:
        return True
    if member.get("internal"):
        return False
    return member["visibility"] == "public" or (member["visibility"] == "protected" and not cls["final"])


def label(cls):
    return "%s `%s`" % (cls["kind"], cls["fqcn"])


def change(kind, reason, line, symbol, what, text):
    return {"kind": kind, "reason": reason, "line": line, "symbol": symbol, "change": what, "text": text}


def signature_diff(before, after, member=True):
    """[difference] between two signatures, in words."""
    out = []
    if member:
        if before.get("static") != after.get("static"):
            out.append("became static" if after.get("static") else "no longer static")
        if after.get("final") and not before.get("final"):
            out.append("became final: overrides break")
        if after.get("abstract") and not before.get("abstract"):
            out.append("became abstract")
    bp, hp = before["params"], after["params"]
    for n, p in enumerate(bp):
        if n >= len(hp):
            out.append("parameter `%s` removed" % p["name"])
            continue
        q = hp[n]
        if p["variadic"] and not q["variadic"]:
            out.append("`%s` is no longer variadic" % p["name"])
        if p["name"] != q["name"]:
            out.append("parameter `%s` renamed `%s`: named arguments break" % (p["name"], q["name"]))
        if p["type"] != q["type"]:
            out.append("type of `%s` %s -> %s" % (q["name"], p["type"] or "none", q["type"] or "none"))
        if p["default"] and not q["default"] and not q["variadic"]:
            out.append("`%s` lost its default: calls that omit it break" % q["name"])
        if p["byref"] != q["byref"]:
            out.append("`%s` %s by reference" % (q["name"], "now passed" if q["byref"] else "no longer passed"))
    for q in hp[len(bp):]:
        if not q["default"] and not q["variadic"]:
            out.append("new required parameter `%s`" % q["name"])
    if before["returns"] != after["returns"]:
        out.append("return type %s -> %s" % (before["returns"] or "none", after["returns"] or "none"))
    return out


def renamed(gone, new):
    """The one new name beside the one gone, or None."""
    return new[0] if len(gone) == 1 and len(new) == 1 else None


def api_changes(base, head):
    """[change] between the base and head Units of one file (either may be
    None): what consumers outside the diff can break on. Each change has
    `kind`, `reason`, `line` (in the head, or None), `symbol`, `change`
    (`removed` or `signature`) and `text`, the declaration's line."""
    out = []
    b_classes = {k: c for k, c in (base.classes.items() if base else []) if visible(c)}
    h_classes = head.classes if head else {}
    gone = [k for k in b_classes if k not in h_classes]
    new = [k for k, c in h_classes.items() if k not in (base.classes if base else {}) and visible(c)]
    for k in gone:
        c = b_classes[k]
        to = renamed(gone, new)
        reason = "%s removed" % label(c)
        line, text = None, base.text(c["line"])
        if to:
            reason += "; %s appears in its place, a rename" % label(h_classes[to])
            line, text = h_classes[to]["line"], head.text(h_classes[to]["line"])
        out.append(change("class-removed", reason, line, c["name"], "removed", text))
    for k, b in b_classes.items():
        h = h_classes.get(k)
        if h is None:
            continue
        out += class_changes(base, head, b, h)
    b_fns = {k: f for k, f in (base.functions.items() if base else []) if not f["internal"]}
    h_fns = head.functions if head else {}
    gone = [k for k in b_fns if k not in h_fns]
    new = [k for k in h_fns if k not in b_fns]
    for k in gone:
        f, to = b_fns[k], renamed(gone, new)
        reason = "function `%s()` removed" % f["fqcn"]
        line, text = None, base.text(f["line"])
        if to:
            reason += "; `%s()` appears in its place, a rename" % h_fns[to]["fqcn"]
            line, text = h_fns[to]["line"], head.text(h_fns[to]["line"])
        out.append(change("function-removed", reason, line, f["name"], "removed", text))
    for k, f in b_fns.items():
        if k in h_fns:
            diff = signature_diff(f, h_fns[k], member=False)
            if diff:
                g = h_fns[k]
                out.append(change("signature-changed", "function `%s()`: %s" % (g["fqcn"], "; ".join(diff)),
                                  g["line"], g["name"], "signature", head.text(g["line"])))
    return out


def class_changes(base, head, b, h):
    out, where = [], "%s::%%s" % b["name"]
    if b["kind"] != h["kind"]:
        out.append(change("class-changed", "%s became %s %s" % (label(b), "an" if h["kind"][0] in "aeiou" else "a",
                                                                 h["kind"]),
                          h["line"], b["name"], "signature", head.text(h["line"])))
    if h["final"] and not b["final"]:
        out.append(change("class-changed", "%s became final: subclasses outside the diff break" % label(b),
                          h["line"], b["name"], "signature", head.text(h["line"])))
    if h["abstract"] and not b["abstract"] and b["kind"] == h["kind"] == "class":
        out.append(change("class-changed", "%s became abstract: `new %s` breaks" % (label(b), b["name"]),
                          h["line"], b["name"], "signature", head.text(h["line"])))
    for rel in ("extends", "implements"):
        lost = [x for x in b[rel] if x not in h[rel]]
        if lost:
            out.append(change("class-changed", "%s no longer %s %s: type checks on it break" % (
                label(b), rel, ", ".join("`%s`" % x for x in lost)), h["line"], b["name"], "signature",
                head.text(h["line"])))
    b_methods = {k: m for k, m in b["methods"].items() if visible(b, m)}
    gone = [k for k in b_methods if k not in h["methods"]]
    new = [k for k, m in h["methods"].items() if k not in b["methods"] and visible(h, m)]
    for k in gone:
        m, to = b_methods[k], renamed(gone, new)
        reason = "%s method `%s()` removed" % (m["visibility"], where % m["name"])
        line, text = h["line"], base.text(m["line"])
        if to:
            reason += "; `%s()` appears in its place, a rename" % (where % h["methods"][to]["name"])
            line, text = h["methods"][to]["line"], head.text(h["methods"][to]["line"])
        out.append(change("method-removed", reason, line, where % m["name"], "removed", text))
    for k, m in b_methods.items():
        n = h["methods"].get(k)
        if n is None:
            continue
        if not visible(h, n):
            out.append(change("visibility-reduced", "method `%s()` %s -> %s" % (
                where % m["name"], m["visibility"], n["visibility"]), n["line"], where % m["name"], "removed",
                head.text(n["line"])))
            continue
        diff = signature_diff(m, n)
        if diff:
            out.append(change("signature-changed", "%s method `%s()`: %s" % (
                n["visibility"], where % n["name"], "; ".join(diff)), n["line"], where % n["name"], "signature",
                head.text(n["line"])))
    if not h["final"]:
        for k, n in h["methods"].items():
            if k in b["methods"] or not n["abstract"] or not visible(h, n):
                continue
            kind = "interface-method-added" if h["kind"] == "interface" else "abstract-method-added"
            who = "implementations" if h["kind"] == "interface" else "subclasses"
            out.append(change(kind, "%s method `%s()` added: %s outside the diff must define it" % (
                "interface" if h["kind"] == "interface" else "abstract", where % n["name"], who),
                n["line"], where % n["name"], "signature", head.text(n["line"])))
    for k, cst in b["constants"].items():
        if not visible(b, cst):
            continue
        what = "case" if cst["case"] else "constant"
        n = h["constants"].get(k)
        if n is None or not visible(h, n):
            out.append(change("constant-removed", "%s `%s` %s" % (what, where % k, "removed" if n is None else
                                                                   "is no longer public"),
                              n["line"] if n else h["line"], where % k, "removed",
                              head.text(n["line"]) if n else base.text(cst["line"])))
    for k, p in b["properties"].items():
        if not visible(b, p):
            continue
        n = h["properties"].get(k)
        if n is None or not visible(h, n):
            out.append(change("property-removed", "property `%s` %s" % (
                where % ("$" + k), "removed" if n is None else "%s -> %s" % (p["visibility"], n["visibility"])),
                n["line"] if n else h["line"], where % ("$" + k), "removed",
                head.text(n["line"]) if n else base.text(p["line"])))
            continue
        diff = []
        if p["type"] != n["type"]:
            diff.append("type %s -> %s" % (p["type"] or "none", n["type"] or "none"))
        if n["readonly"] and not p["readonly"]:
            diff.append("became readonly: writes outside the class break")
        if p["static"] != n["static"]:
            diff.append("became static" if n["static"] else "no longer static")
        if diff:
            out.append(change("property-changed", "property `%s`: %s" % (where % ("$" + k), "; ".join(diff)),
                              n["line"], where % ("$" + k), "signature", head.text(n["line"])))
    return out


# --- Fan-in -----------------------------------------------------------------------

def symbols(base, head, changed_lines):
    """[{symbol, change, line}]: the public symbols a file's diff removes,
    changes or edits the body of (a method the base already had: a new one
    has no caller to count). `changed_lines` are the head lines its hunks
    touch."""
    out, seen = [], set()
    for ch in api_changes(base, head):
        if ch["symbol"] not in seen:
            seen.add(ch["symbol"])
            out.append({"symbol": ch["symbol"], "change": ch["change"], "line": ch["line"]})
    if head is None:
        return out
    lines = sorted(set(changed_lines))

    def touched(start, end):
        k = bisect.bisect_left(lines, start)
        return k < len(lines) and lines[k] <= (end or start)

    before = base.classes if base else {}
    for fqcn, cls in head.classes.items():
        if not visible(cls) or fqcn not in before:
            continue
        for k, m in cls["methods"].items():
            name = "%s::%s" % (cls["name"], m["name"])
            if visible(cls, m) and k in before[fqcn]["methods"] and name not in seen \
                    and touched(m["line"], m.get("end")):
                seen.add(name)
                out.append({"symbol": name, "change": "body", "line": m["line"]})
    for k, f in head.functions.items():
        if k in (base.functions if base else {}) and not f["internal"] and f["name"] not in seen \
                and touched(f["line"], f.get("end")):
            seen.add(f["name"])
            out.append({"symbol": f["name"], "change": "body", "line": f["line"]})
    return out


def reference(symbol):
    """(word the line must hold, pattern of a reference) for a symbol of
    `symbols`: `Class::method` matches `->method(` and `::method(`,
    `Class::$prop` matches `->prop` and `::$prop`, `Class::CONST` matches
    `::CONST`, `Class::__construct` matches `new Class(`, a bare name
    matches it as a word (a class) or a call."""
    cls, sep, member = symbol.partition("::")
    if not sep:
        return cls, re.compile(r"(?<![\w$>:])%s\b" % re.escape(cls))
    if member.lower() == "__construct":
        return cls, re.compile(r"\bnew\s+\\?(?:[A-Za-z_]\w*\\)*%s\s*\(" % re.escape(cls))
    if member.startswith("$"):
        name = member[1:]
        return name, re.compile(r"(?:->|\?->)\s*%s\b(?!\s*\()|::\s*\$%s\b" % (re.escape(name), re.escape(name)))
    if re.match(r"^[A-Z][A-Z0-9_]*$", member):
        return member, re.compile(r"::\s*%s\b(?!\s*\()" % re.escape(member))
    return member, re.compile(r"(?:->|\?->|::)\s*%s\s*\(" % re.escape(member), re.I)


def member_name(symbol):
    """The name a fan-in count stands on: the member of `Class::member`,
    the class for its constructor."""
    cls, _, member = symbol.partition("::")
    return cls if member.lower() == "__construct" else member.lstrip("$") or symbol


# --- The import graph ---------------------------------------------------------------

DECLARATION_LINE = re.compile(r"^(?:(?:abstract|final|readonly)\s+)*(?:class|interface|trait|enum|function)\s+\w",
                              re.I)


def quick_imports(text):
    """(namespaces, [(kind, fqcn, line)]): the namespace and top-level
    `use` statements of a file, read line by line until its first
    declaration. For the files the diff does not touch: cheaper than
    `parse`, and enough for the graph."""
    namespaces, imports, buf, start = [], [], None, 0
    for n, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if buf is not None:
            buf += " " + s
            if ";" in s:
                imports += use_statement(buf, start)
                buf = None
            continue
        if DECLARATION_LINE.match(line):
            break
        m = re.match(r"^namespace\s+([\w\\]+)\s*[;{]", s)
        if m:
            namespaces.append(m.group(1).lstrip("\\"))
        elif re.match(r"^use\s+[\\\w]", s) and not line[:1].isspace():
            if ";" in s:
                imports += use_statement(s, n)
            else:
                buf, start = s, n
    return namespaces, imports


def use_statement(text, line):
    """[(kind, fqcn, line)] of one `use ...;` statement."""
    try:
        unit = Unit("<?php\n" + text.split(";", 1)[0] + ";\n")
    except ParseError:
        return []
    return [(k, f, line) for k, f, _ in unit.imports]


class Modules:
    """Which module a namespace belongs to. With PSR-4 prefixes from
    `composer.json` (`autoload` and `autoload-dev`), the segment under the
    longest matching prefix; a class right under the prefix belongs to the
    prefix's own module. Without them, the first two segments of a
    namespace whose first segment the repository declares."""

    def __init__(self, composer_text, declared):
        self.prefixes, self.rule = [], None
        try:
            data = json.loads(composer_text) if composer_text else {}
        except ValueError:
            data = {}
        for section in ("autoload", "autoload-dev"):
            psr4 = (data.get(section) or {}).get("psr-4") if isinstance(data.get(section), dict) else None
            for prefix in (psr4 or {}) if isinstance(psr4, dict) else ():
                p = prefix.strip("\\")
                if p and p not in self.prefixes:
                    self.prefixes.append(p)
        self.prefixes.sort(key=len, reverse=True)
        self.roots = sorted({ns.split("\\", 1)[0] for ns in declared if ns})
        if self.prefixes:
            self.rule = "the namespace segment under a PSR-4 prefix of composer.json (%s)" % ", ".join(
                "`%s\\`" % p for p in sorted(self.prefixes))
        else:
            self.rule = "the first two namespace segments (no PSR-4 prefix in composer.json)"

    def of(self, fqcn):
        """The module of a class, function or constant name, None outside
        the repository."""
        fqcn = fqcn.lstrip("\\")
        if self.prefixes:
            for p in self.prefixes:
                if fqcn.startswith(p + "\\"):
                    rest = fqcn[len(p) + 1:]
                    return p + "\\" + rest.split("\\", 1)[0] if "\\" in rest else p
            return None
        parts = fqcn.split("\\")
        if len(parts) < 2 or parts[0] not in self.roots:
            return None
        return "\\".join(parts[:2]) if len(parts) > 2 else parts[0]

    def of_namespace(self, ns):
        return self.of(ns + "\\_") if ns else None
