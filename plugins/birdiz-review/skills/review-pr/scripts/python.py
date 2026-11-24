"""The Python adapter: what the review reads in Python code without running it.

- `parse`: the declarations of one file (its imports, and the functions,
  classes, variables and re-exports of its module), from the standard `ast`
  module of the interpreter that runs the review. A file that interpreter
  can't parse (syntax newer than it, Python 2) raises `ParseError`: the
  detectors then say they could not cover it.
- `api_changes`: the signature-level diff of a module's public names
  between a file's base and head, labelled heuristic by its detector.
  Public means listed in a static `__all__`, else not starting with `_`; a
  module whose path has a `_private` part exports only its `__all__`.
  Python calls pass arguments by keyword, so a renamed parameter is a
  change; a type is compared as written, only when both sides have one.
- `symbols`, `reference`, `member_name`: the names the diff removes or
  changes, for fan-in, with the pattern their references match; `strip`
  blanks the strings and comments of a file before it is searched.
- `Project` and `quick_imports`: the import graph's nodes. Which file an
  import resolves to (the repository's packages, found through their
  `__init__.py`, under the root, `src/` or a project directory), and which
  module a file belongs to.
- `griffe_breakages` and `linter_report`: what `griffe check` and
  `lint-imports` print, read back.

griffe runs only on a scratch repository the run builds from the two trees,
and import-linter only on a config that loads no project code (see
`detectors.ADAPTERS`).
"""
import ast
import bisect
import io
import posixpath
import re
import sys
import token
import tokenize

INTERPRETER = "Python %d.%d" % sys.version_info[:2]
ENUM_BASES = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "ReprEnum"}
VARIADIC = ("vararg", "kwarg")
POSITIONAL = ("posonly", "pos")
PROJECT_FILES = ("pyproject.toml", "setup.py", "setup.cfg")
STDLIB = frozenset(getattr(sys, "stdlib_module_names", ())) or frozenset(
    "abc ast asyncio base64 collections copy csv dataclasses datetime decimal email enum functools glob hashlib http"
    " importlib inspect io itertools json logging math os pathlib pickle platform queue random re shutil signal"
    " socket sqlite3 string subprocess sys tempfile threading time tomllib types typing unittest urllib uuid warnings"
    " xml zipfile".split())
NOT_PROJECT = {"tests", "test", "testing", "docs", "doc", "examples", "example", "scripts", "benchmarks", "bench",
               "tools", "conftest"}


class ParseError(Exception):
    pass


def is_code(path):
    return path.lower().endswith(".py")


def unparse(node):
    return ast.unparse(node) if node is not None else None


def annotation(node):
    """An annotation as written, a string annotation read as the code it
    holds."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return ast.unparse(ast.parse(node.value, mode="eval").body)
        except SyntaxError:
            return node.value
    return ast.unparse(node)


def last(name):
    """`typing.overload` -> `overload`, `dataclass(frozen=True)` -> `dataclass`."""
    return name.split("(", 1)[0].split("[", 1)[0].rsplit(".", 1)[-1]


def dunder(name):
    return name.startswith("__") and name.endswith("__") and len(name) > 4


def member_public(name):
    return dunder(name) or not name.startswith("_")


def private_path(path):
    """A module under a `_private` part of its path."""
    for part in (path or "").split("/"):
        stem = part[:-3] if part.endswith(".py") else part
        if stem.startswith("_") and not dunder(stem):
            return True
    return False


def statements(body):
    """Every statement of a body, nested ones included (if, try, with,
    match, and the bodies of functions and classes)."""
    stack = list(reversed(body))
    while stack:
        node = stack.pop()
        yield node
        for field in ("body", "orelse", "finalbody", "handlers", "cases"):
            sub = getattr(node, field, None)
            if isinstance(sub, list):
                stack.extend(reversed(sub))


def imports_of(tree):
    """[(level, module, names, line)] of every import statement."""
    out = []
    for node in statements(tree.body):
        if isinstance(node, ast.Import):
            out += [(0, a.name, [], node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            out.append((node.level or 0, node.module or "", [a.name for a in node.names], node.lineno))
    return out


def tree_of(text, path):
    try:
        return ast.parse(text, filename=path or "<unknown>")
    except SyntaxError as e:
        raise ParseError("%s (line %s)" % (e.msg, e.lineno))
    except (ValueError, RecursionError, MemoryError) as e:
        raise ParseError(str(e) or e.__class__.__name__)


# --- Declarations ---------------------------------------------------------------------

def param(arg, kind, default):
    return {"name": arg.arg, "kind": kind, "default": unparse(default), "type": annotation(arg.annotation)}


def tparams(node):
    found = getattr(node, "type_params", None) or []
    return ", ".join(ast.unparse(t) for t in found) or None


def signature(node, method=False):
    a = node.args
    posonly = list(getattr(a, "posonlyargs", []))
    plain = posonly + list(a.args)
    defaults = [None] * (len(plain) - len(a.defaults)) + list(a.defaults)
    params = [param(arg, "posonly" if i < len(posonly) else "pos", defaults[i]) for i, arg in enumerate(plain)]
    if a.vararg:
        params.append(param(a.vararg, "vararg", None))
    params += [param(arg, "kwonly", d) for arg, d in zip(a.kwonlyargs, a.kw_defaults)]
    if a.kwarg:
        params.append(param(a.kwarg, "kwarg", None))
    if method and params and params[0]["kind"] in POSITIONAL:
        params = params[1:]  # self or cls
    return {"params": params, "returns": annotation(node.returns), "async": isinstance(node, ast.AsyncFunctionDef),
            "tparams": tparams(node), "line": node.lineno}


def decorators(node):
    return [ast.unparse(d) for d in node.decorator_list]


class Unit:
    """The declarations of one Python file."""

    def __init__(self, text, path):
        tree = tree_of(text, path)
        self.lines = text.split("\n")
        self.path = path or ""
        self.package_init = posixpath.basename(self.path) == "__init__.py"
        self.private = private_path(self.path)
        self.api, self.all, self.all_dynamic, self.all_line = {}, None, False, None
        self._overloads = {}
        try:
            self._module(tree.body)
            self.imports = imports_of(tree)
        except RecursionError:
            raise ParseError("an expression too deeply nested to read")

    def text(self, line):
        return self.lines[line - 1].strip() if line and 0 < line <= len(self.lines) else ""

    def public(self, name):
        if self.all is not None and not self.all_dynamic:
            return name in self.all
        if self.private or name.startswith("_"):
            return False
        d = self.api.get(name)
        return d is None or d["kind"] != "alias" or d["explicit"]

    # module level

    def _module(self, body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._function(node)
            elif isinstance(node, ast.ClassDef):
                self.api[node.name] = self._class(node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                self._assign(node)
            elif isinstance(node, ast.Expr):
                self._all_call(node.value)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self._alias(node)
            elif node.__class__.__name__ == "TypeAlias":
                self.api[node.name.id] = {"kind": "type", "text": ast.unparse(node.value), "tparams": tparams(node),
                                          "line": node.lineno}
            elif isinstance(node, ast.If):
                self._module(node.body)
                self._module(node.orelse)
            elif isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                self._module(node.body)
                for h in node.handlers:
                    self._module(h.body)
                self._module(node.orelse)
                self._module(node.finalbody)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                self._module(node.body)

    def _function(self, node):
        sig = signature(node)
        decos = [last(d) for d in decorators(node)]
        if "overload" in decos:
            self._overloads.setdefault(node.name, []).append(sig)
            sigs = list(self._overloads[node.name])
        else:
            sigs = self._overloads.pop(node.name, []) + [dict(sig, body=True)]
        self.api[node.name] = {"kind": "function", "sigs": sigs, "line": node.lineno,
                               "end": getattr(node, "end_lineno", None)}

    def _names(self, target):
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            return [n for t in target.elts for n in self._names(t)]
        return []

    @staticmethod
    def _strings(node):
        if isinstance(node, (ast.List, ast.Tuple)) and all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
            return [e.value for e in node.elts]
        return None

    def _assign(self, node):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            for name in self._names(target):
                if name == "__all__":
                    found = self._strings(value) if value is not None else None
                    if isinstance(node, ast.AugAssign) and found is not None and self.all is not None:
                        self.all += found
                    elif not isinstance(node, ast.AugAssign) and found is not None:
                        self.all, self.all_line = found, node.lineno
                    else:
                        self.all_dynamic = True
                    continue
                if isinstance(node, ast.AugAssign):
                    continue
                type_ = annotation(node.annotation) if isinstance(node, ast.AnnAssign) else None
                self.api[name] = {"kind": "variable", "type": type_, "line": node.lineno}

    def _all_call(self, call):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "__all__"):
            return
        args = call.args
        found = None
        if call.func.attr == "extend" and len(args) == 1:
            found = self._strings(args[0])
        elif call.func.attr == "append" and len(args) == 1 and isinstance(args[0], ast.Constant) \
                and isinstance(args[0].value, str):
            found = [args[0].value]
        if found is not None and self.all is not None:
            self.all += found
        else:
            self.all_dynamic = True

    def _alias(self, node):
        for a in node.names:
            if a.name == "*":
                continue
            if isinstance(node, ast.Import):
                name = a.asname or a.name.split(".")[0]
                target = a.name
                explicit = a.asname is not None and a.asname == a.name
            else:
                name = a.asname or a.name
                target = "%s%s.%s" % ("." * (node.level or 0), node.module or "", a.name)
                explicit = (a.asname is not None and a.asname == a.name) or bool(node.level and self.package_init)
            self.api[name] = {"kind": "alias", "target": target, "explicit": explicit, "line": node.lineno}

    # classes

    def _class(self, node):
        decos = decorators(node)
        names = [last(d) for d in decos]
        bases = [ast.unparse(b) for b in node.bases]
        kinds = {last(b) for b in bases}
        enum = bool(kinds & ENUM_BASES)
        members, fields = {}, []
        dataclass = "dataclass" in names and not any(
            re.search(r"\binit\s*=\s*False\b", d) for d in decos if last(d) == "dataclass")
        kw_all = any(re.search(r"\bkw_only\s*=\s*True\b", d) for d in decos if last(d) == "dataclass")
        self._body(node.body, members, fields, enum)
        init = next((n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.name == "__init__"), None)
        if init is not None:
            self._instance_attributes(init, members)
        if (dataclass or "NamedTuple" in kinds) and "__init__" not in members:
            members["__init__"] = {"kind": "method", "sigs": [self._fields_signature(node, fields, kw_all)],
                                   "line": node.lineno, "synthetic": True}
        if enum:
            self._enum_values(members, kinds)
        return {"kind": "class", "line": node.lineno, "end": getattr(node, "end_lineno", None), "bases": bases,
                "members": members, "enum": enum, "protocol": "Protocol" in kinds, "final": "final" in names}

    def _body(self, body, members, fields, enum):
        overloads = {}
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._method(node, members, overloads)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                type_ = annotation(node.annotation) if isinstance(node, ast.AnnAssign) else None
                for target in targets:
                    for name in self._names(target):
                        if enum and not name.startswith("_") and node.value is not None:
                            members[name] = {"kind": "member", "value": unparse(node.value), "line": node.lineno}
                        else:
                            members[name] = {"kind": "attribute", "type": type_, "line": node.lineno}
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    fields.append(node)
            elif isinstance(node, ast.ClassDef):
                members[node.name] = {"kind": "class", "line": node.lineno}
            elif isinstance(node, ast.If):
                self._body(node.body + node.orelse, members, fields, enum)
            elif isinstance(node, ast.Try):
                self._body(node.body + [s for h in node.handlers for s in h.body] + node.orelse, members, fields,
                           enum)

    def _method(self, node, members, overloads):
        decos = decorators(node)
        names = [last(d) for d in decos]
        for d in decos:
            m = re.match(r"^(\w+)\.(setter|deleter)$", d)
            if m:
                if m.group(2) == "setter" and members.get(m.group(1), {}).get("kind") == "property":
                    members[m.group(1)]["settable"] = True
                return
        end = getattr(node, "end_lineno", None)
        abstract = any(n in ("abstractmethod", "abstractproperty") for n in names)
        if any(n in ("property", "cached_property", "abstractproperty") for n in names):
            members[node.name] = {"kind": "property", "type": annotation(node.returns), "settable": False,
                                  "line": node.lineno, "end": end, "abstract": abstract}
            return
        sig = signature(node, method="staticmethod" not in names)
        if "overload" in names:
            overloads.setdefault(node.name, []).append(sig)
            sigs = list(overloads[node.name])
        else:
            sigs = overloads.pop(node.name, []) + [dict(sig, body=True)]
        members[node.name] = {"kind": "method", "sigs": sigs, "line": node.lineno, "end": end, "abstract": abstract}

    def _instance_attributes(self, init, members):
        args = list(getattr(init.args, "posonlyargs", [])) + list(init.args.args)
        if not args:
            return
        me = args[0].arg
        stack = list(init.body)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == me \
                            and t.attr not in members:
                        type_ = annotation(node.annotation) if isinstance(node, ast.AnnAssign) else None
                        members[t.attr] = {"kind": "attribute", "type": type_, "line": node.lineno}
            stack.extend(ast.iter_child_nodes(node))

    @staticmethod
    def _fields_signature(node, fields, kw_all):
        params, kw = [], kw_all
        for f in fields:
            type_ = annotation(f.annotation) or ""
            if last(type_) == "KW_ONLY":
                kw = True
                continue
            if last(type_) == "ClassVar":
                continue
            default, kw_field = unparse(f.value), kw
            if isinstance(f.value, ast.Call) and last(ast.unparse(f.value.func)) == "field":
                opts = {k.arg: k.value for k in f.value.keywords if k.arg}
                if isinstance(opts.get("init"), ast.Constant) and opts["init"].value is False:
                    continue
                if "default" in opts:
                    default = ast.unparse(opts["default"])
                elif "default_factory" in opts:
                    default = "%s()" % ast.unparse(opts["default_factory"])
                else:
                    default = None
                if isinstance(opts.get("kw_only"), ast.Constant):
                    kw_field = bool(opts["kw_only"].value)
            params.append({"name": f.target.id, "kind": "kwonly" if kw_field else "pos", "default": default,
                           "type": annotation(f.annotation)})
        return {"params": params, "returns": None, "async": False, "tparams": None, "line": node.lineno}

    @staticmethod
    def _enum_values(members, kinds):
        """The value of each `auto()` member, as Python 3.13 numbers them:
        the highest value so far plus one, the next power of two for a
        flag, the lowercased name for a `StrEnum`."""
        highest, flag, text = None, bool(kinds & {"Flag", "IntFlag"}), "StrEnum" in kinds
        for name, m in members.items():
            if m["kind"] != "member":
                continue
            value = m["value"]
            if value is not None and re.match(r"^(enum\.)?auto\(\)$", value):
                if text:
                    m["value"] = repr(name.lower())
                    continue
                if flag:
                    n = 1 if not highest or highest < 1 else 1 << highest.bit_length()
                else:
                    n = 1 if highest is None else highest + 1
                m["value"] = str(n)
            else:
                n = int_value(value)
            if n is not None:
                highest = n if highest is None else max(highest, n)


INT_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.LShift: lambda a, b: a << b if b < 64 else None, ast.BitOr: lambda a, b: a | b}


def int_value(text):
    """The integer an enum value's text is (`3`, `1 << 3`, `A_FLAG | 4`
    aside), or None."""
    def ev(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            v = ev(node.operand)
            return -v if v is not None else None
        if isinstance(node, ast.BinOp) and type(node.op) in INT_OPS:
            a, b = ev(node.left), ev(node.right)
            return INT_OPS[type(node.op)](a, b) if a is not None and b is not None and b >= 0 else None
        return None
    try:
        return ev(ast.parse(text, mode="eval").body) if text else None
    except (SyntaxError, ValueError, RecursionError):
        return None


def parse(text, path):
    """The declarations of a Python file's text; raises ParseError."""
    return Unit(text, path)


# --- The public API diff -----------------------------------------------------------

def change(kind, reason, line, symbol, what, text):
    return {"kind": kind, "reason": reason, "line": line, "symbol": symbol, "change": what, "text": text}


def renamed(gone, new):
    return new[0] if len(gone) == 1 and len(new) == 1 else None


def category(d):
    return {"alias": "value", "variable": "value"}.get(d["kind"], d["kind"])


WORDS = {"function": "a function", "class": "a class", "value": "a value", "type": "a type alias"}
REMOVED = {"function": "function-removed", "class": "class-removed"}


def describe(d, name):
    return {"function": "function `%s()`", "class": "class `%s`", "alias": "re-export `%s`",
            "type": "type alias `%s`"}.get(d["kind"], "name `%s`") % name


def api_sigs(sigs):
    """The signatures callers see: the overloads, when a function has some."""
    declared = [s for s in sigs if not s.get("body")]
    return declared or sigs[-1:]


def sig_text(sig):
    marks = {"vararg": "*", "kwarg": "**"}
    return "(%s)%s" % (", ".join("%s%s%s%s" % (marks.get(p["kind"], ""), p["name"],
                                               ": " + p["type"] if p["type"] else "",
                                               "=" + p["default"] if p["default"] else "") for p in sig["params"]),
                       " -> " + sig["returns"] if sig["returns"] else "")


def sig_diff(before, after):
    """[difference] between two signatures, in words, as calls see them:
    by position and by keyword."""
    out = []
    bp, hp = before["params"], after["params"]
    bnames, hnames = {p["name"]: p for p in bp}, {p["name"]: p for p in hp}
    h_var = any(p["kind"] == "vararg" for p in hp)
    h_kw = any(p["kind"] == "kwarg" for p in hp)
    bpos, hpos = [p for p in bp if p["kind"] in POSITIONAL], [p for p in hp if p["kind"] in POSITIONAL]
    if (before.get("tparams") or None) != (after.get("tparams") or None):
        out.append("type parameters [%s] -> [%s]" % (before.get("tparams") or "", after.get("tparams") or ""))
    renames = {}
    for i, p in enumerate(bpos):
        if p["name"] not in hnames and i < len(hpos) and hpos[i]["name"] not in bnames:
            renames[p["name"]] = hpos[i]["name"]
    for p in bp:
        name = p["name"]
        if p["kind"] == "vararg":
            if not h_var:
                out.append("`*%s` removed: calls passing extra positional arguments break" % name)
            continue
        if p["kind"] == "kwarg":
            if not h_kw:
                out.append("`**%s` removed: calls passing extra keyword arguments break" % name)
            continue
        q = hnames.get(name)
        if q is None and name in renames:
            q = hnames[renames[name]]
            if p["kind"] != "posonly" and (not h_kw or q["default"] is None):
                out.append("parameter `%s` renamed `%s`: calls passing it by keyword break" % (name, q["name"]))
        elif q is None:
            absorbed = (p["kind"] == "kwonly" and h_kw) or (p["kind"] == "posonly" and h_var) or (
                p["kind"] == "pos" and h_var and h_kw)
            if not absorbed:
                out.append("parameter `%s` removed" % name)
            continue
        shown = q["name"]
        if p["kind"] != q["kind"]:
            if q["kind"] == "kwonly":
                out.append("`%s` became keyword-only: calls passing it by position break" % shown)
            elif q["kind"] == "posonly":
                out.append("`%s` became positional-only: calls passing it by keyword break" % shown)
            elif q["kind"] in VARIADIC:
                out.append("`%s` became `%s%s`" % (shown, "*" if q["kind"] == "vararg" else "**", shown))
        if p["kind"] in POSITIONAL and q["kind"] in POSITIONAL and bpos.index(p) != hpos.index(q):
            out.append("positional parameter `%s` moved from position %d to %d" % (
                shown, bpos.index(p) + 1, hpos.index(q) + 1))
        if q["kind"] not in VARIADIC:
            if p["default"] is not None and q["default"] is None:
                out.append("`%s` became required: calls that omit it break" % shown)
            elif p["default"] is not None and p["default"] != q["default"]:
                out.append("default of `%s` %s -> %s" % (shown, p["default"], q["default"]))
        if p["type"] and q["type"] and p["type"] != q["type"]:
            out.append("type of `%s` %s -> %s" % (shown, p["type"], q["type"]))
    taken = set(renames.values())
    for q in hp:
        if q["name"] not in bnames and q["name"] not in taken and q["kind"] not in VARIADIC and q["default"] is None:
            out.append("new required parameter `%s`" % q["name"])
    if before["returns"] and after["returns"] and before["returns"] != after["returns"]:
        out.append("return type %s -> %s" % (before["returns"], after["returns"]))
    if before.get("async") != after.get("async"):
        out.append("became async: callers must await it" if after.get("async")
                   else "no longer async: callers that await it break")
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
    b_api = {k: d for k, d in base.api.items() if base.public(k)} if base else {}
    h_api = head.api if head else {}

    def h_public(k):
        return head is not None and k in h_api and head.public(k)

    gone = [k for k in b_api if not h_public(k)]
    new = [k for k in h_api if h_public(k) and k not in b_api]
    for k in gone:
        d = b_api[k]
        still = k in h_api
        to = None if still else renamed(gone, new)
        reason = "%s %s" % (describe(d, k), "removed" if not still else
                            "no longer in `__all__`" if head.all is not None else "is no longer public")
        line, text = None, base.text(d["line"])
        if still:
            line, text = h_api[k]["line"], head.text(h_api[k]["line"])
        if to:
            reason += "; %s appears in its place, a rename" % describe(h_api[to], to)
            line, text = h_api[to]["line"], head.text(h_api[to]["line"])
        out.append(change(REMOVED.get(d["kind"], "name-removed"), reason, line, k, "removed", text))
    if base and head and base.all is not None and head.all is not None and not (base.all_dynamic or head.all_dynamic):
        for k in base.all:  # names `__all__` exports from elsewhere (a star import)
            if k not in base.api and k not in head.all and k not in h_api:
                out.append(change("name-removed", "name `%s` no longer in `__all__`" % k, head.all_line, k, "removed",
                                  head.text(head.all_line)))
    for k, b in b_api.items():
        if h_public(k):
            out += decl_changes(base, head, k, b, h_api[k])
    return out


def decl_changes(base, head, name, b, h):
    cb, ch = category(b), category(h)
    line, text = h["line"], head.text(h["line"])
    if cb != ch:
        return [change("name-changed", "`%s` was %s, now %s" % (name, WORDS[cb], WORDS[ch]), line, name,
                       "signature", text)]
    if cb == "function":
        diff = sigs_diff(b["sigs"], h["sigs"])
        return [change("signature-changed", "function `%s()`: %s" % (name, "; ".join(diff)), line, name,
                       "signature", text)] if diff else []
    if cb == "class":
        return class_changes(base, head, name, b, h)
    if cb == "type":
        diff = []
        if b["tparams"] != h["tparams"]:
            diff.append("type parameters [%s] -> [%s]" % (b["tparams"] or "", h["tparams"] or ""))
        if b["text"] != h["text"]:
            diff.append("%s -> %s" % (b["text"], h["text"]))
        return [change("type-changed", "type alias `%s`: %s" % (name, "; ".join(diff)), line, name, "signature",
                       text)] if diff else []
    if b.get("type") and h.get("type") and b["type"] != h["type"]:
        return [change("name-changed", "name `%s`: type %s -> %s" % (name, b["type"], h["type"]), line, name,
                       "signature", text)]
    return []


def member_label(owner, name, m):
    if name == "__init__":
        return "constructor `%s()`" % owner
    return {"method": "method `%s.%s()`", "property": "property `%s.%s`", "member": "member `%s.%s`",
            "class": "class `%s.%s`"}.get(m["kind"], "attribute `%s.%s`") % (owner, name)


MEMBER_REMOVED = {"method": "method-removed", "member": "enum-member-removed"}
SKIPPED_BASES = {"object", "Generic", "Protocol", "ABC"}


def class_changes(base, head, name, b, h):
    out = []
    line, text = h["line"], head.text(h["line"])
    lost = [x for x in b["bases"] if x not in h["bases"] and last(x) not in SKIPPED_BASES]
    if lost:
        out.append(change("class-changed", "class `%s` no longer inherits %s: isinstance checks and inherited"
                          " members break" % (name, ", ".join("`%s`" % x for x in lost)), line, name, "signature",
                          text))
    if h["final"] and not b["final"]:
        out.append(change("class-changed", "class `%s` became final: subclasses outside the diff break" % name, line,
                          name, "signature", text))
    bm = {k: m for k, m in b["members"].items() if member_public(k)}
    hm = h["members"]
    gone = [k for k in bm if k not in hm]
    new = [k for k, m in hm.items() if k not in b["members"] and member_public(k)]
    methods_gone = [k for k in gone if bm[k]["kind"] == "method"]
    methods_new = [k for k in new if hm[k]["kind"] == "method"]
    for k in gone:
        m = bm[k]
        symbol = "%s.%s" % (name, k)
        reason = "%s removed" % member_label(name, k, m)
        where, shown = line, head.text(line)
        to = renamed(methods_gone, methods_new) if m["kind"] == "method" else None
        if to:
            reason += "; %s appears in its place, a rename" % member_label(name, to, hm[to])
            where, shown = hm[to]["line"], head.text(hm[to]["line"])
        elif k == "__init__":
            reason += ": `%s(...)` now takes what its parent's constructor takes" % name
        out.append(change(MEMBER_REMOVED.get(m["kind"], "property-removed"), reason, where, symbol, "removed",
                          shown))
    for k, m in bm.items():
        n = hm.get(k)
        if n is None:
            continue
        out += member_changes(head, name, k, m, n)
    if not h["final"]:
        for k in new:
            n = hm[k]
            symbol = "%s.%s" % (name, k)
            if n.get("abstract"):
                out.append(change("abstract-method-added", "abstract %s added: subclasses outside the diff must"
                                  " define it" % member_label(name, k, n), n["line"], symbol, "signature",
                                  head.text(n["line"])))
            elif h["protocol"] and not dunder(k):
                out.append(change("protocol-member-added", "protocol %s added: classes outside the diff that"
                                  " satisfy `%s` must define it" % (member_label(name, k, n), name), n["line"],
                                  symbol, "signature", head.text(n["line"])))
    return out


def member_changes(head, owner, name, m, n):
    symbol = "%s.%s" % (owner, name)
    label = member_label(owner, name, n)
    line, text = n["line"], head.text(n["line"])
    if m["kind"] == "member" or n["kind"] == "member":
        if m["kind"] == n["kind"] and m.get("value") != n.get("value"):
            return [change("enum-member-changed", "member `%s` value %s -> %s: stored or sent values change"
                           " meaning" % (symbol, m.get("value"), n.get("value")), line, symbol, "signature", text)]
        return []
    if m["kind"] != n["kind"]:
        calls = {"method": "a method", "property": "a property", "attribute": "an attribute", "class": "a class"}
        return [change("property-changed", "`%s` was %s, now %s" % (symbol, calls[m["kind"]], calls[n["kind"]]),
                       line, symbol, "signature", text)]
    if m["kind"] == "method":
        diff = sigs_diff(m["sigs"], n["sigs"])
        return [change("signature-changed", "%s: %s" % (label, "; ".join(diff)), line, symbol, "signature",
                       text)] if diff else []
    diff = []
    if m["kind"] == "property" and m.get("settable") and not n.get("settable"):
        diff.append("became read-only: writes outside the class break")
    if m.get("type") and n.get("type") and m["type"] != n["type"]:
        diff.append("type %s -> %s" % (m["type"], n["type"]))
    return [change("property-changed", "%s: %s" % (label, "; ".join(diff)), line, symbol, "signature",
                   text)] if diff else []


# --- Fan-in -----------------------------------------------------------------------

def symbols(base, head, changed_lines):
    """[{symbol, change, line}]: the public names and members a file's diff
    removes, changes or edits the body of (one the base already had: a new
    one has no caller to count). `changed_lines` are the head lines its
    hunks touch."""
    out, seen = [], set()
    for ch in api_changes(base, head):
        if ch["symbol"] not in seen:
            seen.add(ch["symbol"])
            out.append({"symbol": ch["symbol"], "change": ch["change"], "line": ch["line"]})
    if head is None or base is None:
        return out
    lines = sorted(set(changed_lines))

    def touched(start, end):
        k = bisect.bisect_left(lines, start)
        return k < len(lines) and lines[k] <= (end or start)

    for k, d in head.api.items():
        b = base.api.get(k)
        if b is None or not head.public(k) or not base.public(k):
            continue
        if d["kind"] == "class" and b["kind"] == "class":
            for mk, m in d["members"].items():
                name = "%s.%s" % (k, mk)
                if m["kind"] in ("method", "property") and member_public(mk) and mk in b["members"] \
                        and not m.get("synthetic") and name not in seen and touched(m["line"], m.get("end")):
                    seen.add(name)
                    out.append({"symbol": name, "change": "body", "line": m["line"]})
        elif d["kind"] == b["kind"] == "function" and k not in seen and touched(d["line"], d.get("end")):
            seen.add(k)
            out.append({"symbol": k, "change": "body", "line": d["line"]})
    return out


def reference(symbol, path=""):
    """(word the line must hold, pattern of a reference) for a symbol of
    `symbols` defined in the file at `path`: `Class.member` matches
    `.member`, `Class.__init__` matches `Class(` and a class that inherits
    it, a bare name matches it as a word or through its module's name
    (`total`, `invoice.total` for `billing/invoice.py`), not as another
    object's attribute (`pickle.dumps` is not `json.dumps`)."""
    owner, sep, member = symbol.partition(".")
    stem = posixpath.basename(posixpath.dirname(path) if path.endswith("/__init__.py") else path)[:-3] \
        if path.endswith(".py") else ""

    def named(name):
        n = re.escape(name)
        if stem and stem.isidentifier():
            return r"(?:(?<![\w.])%s|(?<![\w.])%s\s*\.\s*%s)(?!\w)" % (n, re.escape(stem), n)
        return r"(?<![\w.])%s(?!\w)" % n

    if not sep:
        return owner, re.compile(named(owner))
    if member == "__init__":
        return owner, re.compile(r"%s\s*\(|^\s*class\s+\w+\s*\([^)]*%s" % (named(owner), named(owner)))
    return member, re.compile(r"\.\s*%s(?!\w)" % re.escape(member))


def member_name(symbol):
    """The name a fan-in count stands on: the member of `Class.member`, the
    class for its constructor."""
    owner, _, member = symbol.partition(".")
    return owner if member == "__init__" else member or symbol


BLANKED = {token.STRING, token.COMMENT} | {getattr(token, n) for n in ("FSTRING_MIDDLE", "TSTRING_MIDDLE")
                                          if hasattr(token, n)}


FSTRING_OPEN = re.compile(r"(?i)[rbu]*f[rbu]*('''|\"\"\"|'|\")")


def fstring_code(literal):
    """The offsets of an f-string literal that are code: inside its `{...}`
    fields, `{{` and `}}` being text. Before Python 3.12 the tokenizer gives
    an f-string as one string token."""
    m = FSTRING_OPEN.match(literal)
    if not m:
        return []
    out, depth, i, end = [], 0, m.end(), len(literal) - len(m.group(1))
    while i < end:
        ch = literal[i]
        if depth == 0 and literal[i:i + 2] in ("{{", "}}"):
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
        elif depth:
            out.append(i)
        i += 1
    return out


def strip(text):
    """The text with its strings and comments blanked, lines kept, the code
    of f-strings left; the text as it is when it can't be tokenized."""
    starts = [0]
    for m in re.finditer(r"\n", text):
        starts.append(m.end())
    out = list(text)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type not in BLANKED:
                continue
            (r1, c1), (r2, c2) = tok.start, tok.end
            if r1 > len(starts) or r2 > len(starts):
                continue
            first = starts[r1 - 1] + c1
            keep = {first + k for k in fstring_code(tok.string)} if tok.type == token.STRING else ()
            for i in range(first, min(starts[r2 - 1] + c2, len(out))):
                if out[i] != "\n" and i not in keep:
                    out[i] = " "
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
        return text
    return "".join(out)


# --- The import graph ---------------------------------------------------------------

def quick_imports(text, path):
    """[(level, module, names, line)] of a file the diff does not touch,
    None when it can't be parsed."""
    if "import" not in text:
        return []
    try:
        return imports_of(tree_of(text, path))
    except ParseError:
        return None


class Project:
    """Which file an import resolves to, and which module a file belongs
    to. A file in a package (a directory with `__init__.py`) is named from
    the directory above its topmost package; any other from the closest
    root above it (the repository root, a directory with `pyproject.toml`,
    `setup.py` or `setup.cfg`, or its `src/`). A module is a root's
    top-level package, or its first subpackage when the root has a single
    top-level package (tests, docs and scripts aside); a file outside any
    package belongs to its directory."""

    def __init__(self, files):
        files = sorted(set(files))
        py = [f for f in files if is_code(f)]
        self.inits = {posixpath.dirname(f) for f in py if posixpath.basename(f) == "__init__.py"} - {""}
        roots = {""} | {posixpath.dirname(f) for f in files if posixpath.basename(f) in PROJECT_FILES}
        roots |= {posixpath.join(r, "src") if r else "src" for r in list(roots)
                  if any(f.startswith((posixpath.join(r, "src") if r else "src") + "/") for f in py)}
        self.roots = sorted(roots, key=lambda r: (-len(r), r))
        self.names, self.root_of, self.index, self.packaged, tops = {}, {}, {}, set(), {}
        for f in py:
            name, root, package = self.name_of(f)
            self.names[f], self.root_of[f] = name, root
            self.index.setdefault(name, []).append(f)
            top = name.split(".")[0]
            if package:
                self.packaged.add(f)
                if top not in NOT_PROJECT:
                    tops.setdefault(root, set()).add(top)
        self.single = {r: next(iter(t)) for r, t in tops.items() if len(t) == 1}
        self.rule = ("a root's top-level package (a directory with `__init__.py`, under the repository root, `src/` or"
                     " a project directory), or its first subpackage when the root has one top-level package;"
                     " named by its dotted path, after `<root>:` outside the repository root and `src/`; a file"
                     " outside any package belongs to its directory (`/` for the root)")

    def name_of(self, f):
        """(dotted name, root, in a package) of a file."""
        d, stem = posixpath.dirname(f), posixpath.basename(f)[:-3]
        if d in self.inits:
            top = d
            while posixpath.dirname(top) in self.inits:
                top = posixpath.dirname(top)
            root = posixpath.dirname(top)
            # a namespace package (no `__init__.py`) between a root and the package: named from the root
            root = next((r for r in self.roots if r and root.startswith(r + "/")), root)
            rel = d[len(root) + 1:] if root else d
            return ".".join(rel.split("/") + ([] if stem == "__init__" else [stem])), root, True
        root = next(r for r in self.roots if not r or d == r or d.startswith(r + "/"))
        rel = d[len(root) + 1:] if root and d != root else ("" if d == root else d)
        return ".".join((rel.split("/") if rel else []) + [stem]), root, False

    def package_of(self, path):
        """(root, top-level package) of a file in a package, else None."""
        if path not in self.packaged:
            return None
        return self.root_of[path], self.names[path].split(".")[0]

    def lookup(self, name, root, same_root, exists=None, near=""):
        """The file of a dotted name: under the importer's root, else
        (unless `same_root`) the copy nearest the importer."""
        found = [f for f in self.index.get(name) or [] if exists is None or exists(f)]
        mine = [f for f in found if self.root_of[f] == root]
        if mine or same_root or not found:
            return mine[0] if mine else None
        found = [f for f in found if f in self.packaged and name.split(".")[0] not in STDLIB]  # not a stray script
        return max(found, key=lambda f: len(posixpath.commonpath([f, near])) if near else 0) if found else None

    def local(self, importer, name, exists=None):
        """A module beside a script outside any package (its directory is
        on `sys.path` when it runs)."""
        d = posixpath.dirname(importer)
        if d in self.inits:
            return None
        rel = name.replace(".", "/")
        for p in (posixpath.join(d, rel + ".py"), posixpath.join(d, rel, "__init__.py")):
            if p in self.names and (exists is None or exists(p)):
                return p
        return None

    def resolve(self, importer, level, module, names, exists=None):
        """The repository files an import statement of `importer` loads;
        `exists` tells which files are there on that side."""
        iname, iroot = self.names.get(importer), self.root_of.get(importer)
        if iname is None:
            return []
        if level:
            parts = iname.split(".")
            if posixpath.basename(importer) != "__init__.py":
                parts = parts[:-1]
            if level - 1 >= len(parts):  # beyond the top-level package: an error in Python
                return []
            parts = parts[:len(parts) - (level - 1)]
            base = ".".join(parts + ([module] if module else []))

            def find(n):
                return self.lookup(n, iroot, True, exists)
        else:
            base = module

            def find(n):
                return self.lookup(n, iroot, False, exists, importer) or self.local(importer, n, exists)
        out = []
        if names:
            rest = False
            for n in names:
                t = find("%s.%s" % (base, n) if base else n) if n != "*" else None
                if t:
                    out.append(t)
                else:
                    rest = True
            if rest and base:
                t = find(base)
                if t:
                    out.append(t)
        elif base:
            parts = base.split(".")
            for k in range(len(parts), 0, -1):
                t = find(".".join(parts[:k]))
                if t:
                    out.append(t)
                    break
        return sorted(set(out), key=out.index)

    def module_of(self, path):
        name, root = self.names.get(path), self.root_of.get(path)
        if name is None:
            return None
        if path not in self.packaged:
            return posixpath.dirname(path) or "/"
        dirs = (path[len(root) + 1:] if root else path).split("/")[:-1]
        label = "%s.%s" % (dirs[0], dirs[1]) if self.single.get(root) == dirs[0] and len(dirs) > 1 else dirs[0]
        return label if root in ("", "src") else "%s:%s" % (root, label)

    def file_of(self, module, exists=None):
        """The file of a dotted module name, any root."""
        found = [f for f in self.index.get(module) or [] if exists is None or exists(f)]
        return found[0] if found else None


# --- What the tools print -------------------------------------------------------------

GRIFFE_KINDS = {
    "Positional parameter was moved": "parameter-moved",
    "Parameter was removed": "parameter-removed",
    "Parameter kind was changed": "parameter-kind-changed",
    "Parameter default was changed": "parameter-default-changed",
    "Parameter is now required": "parameter-required",
    "Parameter was added as required": "parameter-added-required",
    "Return types are incompatible": "return-type-changed",
    "Public object was removed": "object-removed",
    "Public object points to a different kind of object": "object-kind-changed",
    "Attribute types are incompatible": "attribute-type-changed",
    "Base class was removed": "base-removed",
    "Attribute value was changed": "attribute-value-changed",
}
GRIFFE_LINE = re.compile(r"^::warning file=(?P<file>[^,]*),line=(?P<line>\d+),title=(?P<title>.*?)::(?P<what>.+)$")


def griffe_breakages(text):
    """[{file, line, title, kind, slug, change}] of what `griffe check -f
    github` printed: one per breakage."""
    out = []
    for raw in text.split("\n"):
        m = GRIFFE_LINE.match(re.sub(r"\x1b\[[0-9;]*m", "", raw.strip()))
        if not m:
            continue
        what, _, detail = m.group("what").partition(": ")
        out.append({"file": m.group("file"), "line": int(m.group("line")) or None, "title": m.group("title"),
                    "kind": what, "slug": GRIFFE_KINDS.get(what, "breakage"), "change": detail})
    return out


CONTRACT_LINE = re.compile(r"^(?P<name>.+?) (?P<result>KEPT|BROKEN)(?: \([^)]*\))?(?: \[[^\]]*\])?$")
SUMMARY_LINE = re.compile(r"^Contracts: (\d+) kept, (\d+) broken\.")
LINK = re.compile(r"(?P<importer>[A-Za-z_][\w.]*) -> (?P<imported>[A-Za-z_][\w.]*) \((?P<lines>l\.[^)]*)\)")


def linter_report(text):
    """{results: {contract: kept|broken}, kept, broken, links: [(contract,
    importer, imported, line)]} of what `lint-imports` printed, None when it
    printed no summary (it failed)."""
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", raw).rstrip() for raw in text.split("\n")]
    summary = next((SUMMARY_LINE.match(x) for x in lines if SUMMARY_LINE.match(x)), None)
    if summary is None:
        return None
    results, links, current, details = {}, [], None, False
    for i, line in enumerate(lines):
        if SUMMARY_LINE.match(line):
            continue
        if not details:
            if line == "Broken contracts" and i + 1 < len(lines) and set(lines[i + 1]) == {"-"}:
                details = True
                continue
            m = CONTRACT_LINE.match(line)
            if m:
                results[m.group("name")] = m.group("result").lower()
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line and nxt and set(nxt) == {"-"} and len(nxt) == len(line):
            current = line
            continue
        for m in LINK.finditer(line):
            n = re.search(r"l\.(\d+)", m.group("lines"))
            links.append((current, m.group("importer"), m.group("imported"), int(n.group(1)) if n else None))
    return {"results": results, "kept": int(summary.group(1)), "broken": int(summary.group(2)), "links": links}
