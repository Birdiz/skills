"""The structure step: what new structure a change brings, visible before
its code is read.

The `structure` detector (`signals/structure.json`, not a content detector,
no signals of its own) writes:

- `new_files`: each file the diff adds, copies or renames, with its class
  (`module`, `layer`, `entry point`, `migration`, `config`, `test`, or
  `source` and `other` for the rest) by path convention, the module it
  belongs to, and whether that module is new;
- `dependencies`: each dependency a changed manifest adds, `D<n>`, with
  its category (HTTP client, validation, state, logging, ...) and the
  dependencies of the same category the manifest already had;
- `domain`: the domain doc read at the base, which names the glossary and
  the ADR directories, then the glossary files and the ADRs at the head;
- `terms`: the type names the diff defines that no glossary term names,
  `T<n>`, for the step to judge as domain terms or not;
- `areas`: the coverage areas whose status is fixed by what exists: no
  stack adapter graph, no glossary, no ADRs, or a contract drift.

An import graph comes from a stack adapter, in one stack-neutral format
(see `graph_output`): the files of each side mapped to modules, and the
file-level import edges. This module computes the new cross-module edges
and the new cycles from it, whatever the stack. Without an adapter, the
Import graph area is `not-evaluable (no stack adapter supplies an import
graph)`.

`findings/structure.md` holds, between its coverage and its findings, three
tables the step fills: `## Dependencies` (`needed` or `not needed`, and
why), `## Terms` (`domain term` or `not a domain term`) and `## Imports`
(`fits` or `boundary`). `run.py` writes every row with `?`.
"""
import fnmatch
import os
import re

from finding_core.markdown import blocks, read
import detectors
import intent
import pocock

AXIS = "structure"
DETECTOR = "structure"
NOT_RUN_YET = intent.NOT_RUN_YET
STEP_FILE = "steps/structure.md"
SECTIONS = ["Dependencies", "Terms", "Imports"]
AREAS = ["New files", "Import graph", "Dependencies", "Pattern divergence", "ADRs", "Glossary"]
CLASSES = ["module", "layer", "entry point", "migration", "config", "test", "source", "other"]
STRUCTURAL = CLASSES[:6]
NEEDED = ["needed", "not needed"]
TERM_JUDGMENTS = ["domain term", "not a domain term"]
IMPORT_JUDGMENTS = ["fits", "boundary"]
GRAPH_PREFIX = "import-graph"
NO_GRAPH = "no stack adapter supplies an import graph"
NO_GLOSSARY = "no glossary"
NO_ADRS = "no ADRs"
FID = intent.FID
UNFILLED = intent.UNFILLED
ROW_ID = re.compile(r"^([DTG])(\d+)\b")

# --- New files ------------------------------------------------------------------

# The first directory under one of these is a module (`src/billing`);
# elsewhere a top-level directory is (`billing`).
SOURCE_ROOTS = {"src", "lib", "libs", "app", "apps", "packages", "internal", "pkg", "modules", "source",
                "plugins", "services", "crates"}
CONFIG_EXTRA = re.compile(
    r"(^|/)(\.github|\.gitlab|\.circleci|\.devcontainer)/"
    r"|(^|/)(\.gitlab-ci\.ya?ml|Dockerfile[\w.-]*|[\w.-]+\.dockerfile|Makefile|Justfile|Procfile|"
    r"[\w.-]+\.config\.(js|cjs|mjs|ts)|tsconfig[\w.-]*\.json|\.[\w.-]+rc(\.(json|ya?ml|js|cjs))?|"
    r"[\w.-]+\.(toml|ini|cfg|conf|neon)|\.editorconfig|\.gitignore|\.gitattributes|\.dockerignore)$")
ENTRY = re.compile(
    r"(^|/)(__main__\.py|manage\.py|wsgi\.py|asgi\.py|artisan|"
    r"main\.(py|go|rs|ts|js|mjs|cjs|kt|java|swift|cs)|cli\.(py|ts|js|mjs|rb|php)|"
    r"server\.(py|ts|js|mjs|go|rb)|app\.(py|ts|js|mjs)|public/index\.php|Program\.cs|views\.py)$"
    r"|(^|/)(bin|cmd|commands?|controllers?|handlers?|Controller|Command|Console)/(.+/)?[^/]+$"
    r"|[^/]*(Controller|Command|Handler|Subscriber|Listener|Consumer)\.(php|java|kt|cs|ts|js|rb|py)$"
    r"|(^|/)[^/]+_(controller|command|handler|job|worker)\.(rb|py|go)$"
    r"|(^|/)[^/]+\.(controller|handler|command|resolver)\.(ts|js)$"
    r"|(^|/)app/(.+/)?page\.(tsx|jsx|ts|js)$")


def module_of(path):
    """The module a path belongs to, None for a file at the root."""
    parts = path.split("/")[:-1]
    if not parts:
        return None
    if parts[0] in SOURCE_ROOTS and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def is_config(path):
    name = os.path.basename(path)
    return bool(detectors.ENV_FILE.search(path) or detectors.CONFIG_FILE.search(path)
                or name in detectors.MANIFESTS or name in detectors.LOCKFILES
                or detectors.REQUIREMENTS.search(path) or CONFIG_EXTRA.search(path))


def classify(path, base_dirs, base_names):
    """(class, why, module, new module) of a new file at `path`. `base_dirs`
    are the directories at the merge base, `base_names` their names."""
    module = module_of(path)
    new_module = bool(module) and module not in base_dirs
    parent = os.path.dirname(path)
    if detectors.is_test(path):
        return "test", "a test file by its path", module, new_module
    kind = detectors.migration_kind(path)
    if kind:
        return "migration", "a %s migration by its path" % kind, module, new_module
    if is_config(path):
        return "config", "a configuration, environment, manifest or build file by its name", module, new_module
    if detectors.ROUTE_FILE.search(path) or detectors.FILE_ROUTE.search(path):
        return "entry point", "a route file: new HTTP surface", module, new_module
    if ENTRY.search(path):
        return "entry point", "an entry point by its name (main, CLI, controller, command, handler)", module, new_module
    if detectors.CODE_EXT.search(path):
        if new_module:
            return "module", "code in the new module `%s/`" % module, module, new_module
        if parent and parent != module and parent not in base_dirs and os.path.basename(parent) not in base_names:
            return ("layer", "a new kind of directory `%s/`: no directory of that name at the base"
                    % os.path.basename(parent), module, new_module)
        return "source", "code in an existing module and directory kind", module, new_module
    return "other", "neither code nor configuration (a document, an asset, data)", module, new_module


def new_files(ctx, base_dirs):
    base_names = {os.path.basename(d) for d in base_dirs}
    out = []
    for c in ctx.changes:
        if c.change not in ("added", "copied", "renamed"):
            continue
        cls, why, module, new_module = classify(c.path, base_dirs, base_names)
        entry = {"path": c.path, "change": c.change, "class": cls, "why": why, "module": module,
                 "new_module": new_module}
        if c.change != "added":
            entry["from"] = c.old
        out.append(entry)
    return out


# --- New dependencies ---------------------------------------------------------------

# Libraries by what they do, across ecosystems: a new one beside one of the
# same category already there is a second way of doing the same thing.
CATEGORIES = {
    "http-client": "axios got node-fetch superagent ky undici cross-fetch isomorphic-fetch ofetch request "
                   "guzzlehttp/guzzle symfony/http-client kriswallsmith/buzz php-http/* requests httpx aiohttp "
                   "urllib3 httplib2 faraday httparty rest-client typhoeus github.com/go-resty/resty* reqwest ureq",
    "validation": "zod yup joi ajv class-validator valibot superstruct io-ts @sinclair/typebox symfony/validator "
                  "respect/validation illuminate/validation webmozart/assert beberlei/assert pydantic marshmallow "
                  "cerberus voluptuous jsonschema dry-validation github.com/go-playground/validator* validator garde",
    "state": "redux @reduxjs/toolkit mobx zustand recoil jotai xstate pinia vuex valtio effector @ngrx/store",
    "logging": "winston pino bunyan log4js loglevel signale consola monolog/monolog loguru structlog logbook "
               "semantic_logger lograge go.uber.org/zap github.com/sirupsen/logrus github.com/rs/zerolog "
               "log tracing env_logger slog",
    "orm": "typeorm prisma @prisma/client sequelize @mikro-orm/* drizzle-orm knex objection mongoose doctrine/orm "
           "illuminate/database propel/propel sqlalchemy peewee tortoise-orm sqlmodel pony activerecord sequel "
           "gorm.io/gorm entgo.io/ent diesel sea-orm",
    "date": "moment dayjs date-fns luxon nesbot/carbon arrow pendulum python-dateutil chrono",
    "test framework": "jest vitest mocha jasmine ava phpunit/phpunit pestphp/pest codeception/codeception pytest "
                      "nose2 rspec minitest",
}
CATALOG = {cat: names.split() for cat, names in CATEGORIES.items()}


def category(name):
    n = name.lower()
    for cat, names in CATALOG.items():
        for pat in names:
            if n == pat or (pat.endswith("*") and n.startswith(pat[:-1])):
                return cat
    return None


def dependencies(ctx):
    """[{did, path, name, spec, line, category, peers}] of the dependencies
    the changed manifests add. Peers are the manifest's other dependencies
    of the same category, already there at the base."""
    out = []
    for c in ctx.changes:
        name = os.path.basename(c.path)
        kind = detectors.MANIFESTS.get(name) or ("requirements" if detectors.REQUIREMENTS.search(c.path) else None)
        if not kind or c.deleted or c.unreadable():
            continue
        try:
            before, _ = detectors.parse_manifest(kind, c.base())
            after, _ = detectors.parse_manifest(kind, c.head())
        except detectors.Unreadable:
            continue  # the dependencies detector reports it not covered
        for dep in sorted(after):
            if dep in before:
                continue
            cat = category(dep)
            peers = sorted(p for p in before if p in after and cat and category(p) == cat)
            out.append({"did": "D%d" % (len(out) + 1), "path": c.path, "name": dep, "spec": after[dep],
                        "line": detectors.line_of(c.head(), dep), "category": cat, "peers": peers})
    return out


# --- The domain doc, the glossary, the ADRs ---------------------------------------

def head_dirs(head_dir):
    out = []
    for d, dirs, _ in os.walk(head_dir):
        dirs[:] = sorted(x for x in dirs if x not in detectors.SKIP_DIRS)
        rel = os.path.relpath(d, head_dir).replace(os.sep, "/")
        if rel != ".":
            out.append(rel)
    return out


def read_head(head_dir, rel):
    path = os.path.join(head_dir, rel)
    if not os.path.isfile(path) or os.path.islink(path):
        return None
    try:
        with open(path, "rb") as fh:
            return detectors.decode(fh.read(detectors.MAX_BYTES * 4))
    except OSError:
        return None


def domain(ctx, domain_text):
    """The domain doc (its text at the base, None when missing), then the
    glossary and the ADRs it names, read in the head tree."""
    head = ctx.head_dir
    map_exists = read_head(head, pocock.GLOSSARY_MAP) is not None
    if domain_text is None:
        doc = {"path": pocock.DOMAIN_DOC, "status": "missing",
               "detail": "no domain doc at the base: Pocock's defaults are read (GLOSSARY.md or GLOSSARY-MAP.md at"
                         " the root, %s/)" % pocock.DEFAULT_ADR_DIR}
        parsed = {"names_glossary": True, "names_map": map_exists, "adr_dirs": [pocock.DEFAULT_ADR_DIR],
                  "glossary_drift": [], "adr_drift": []}
    else:
        parsed = pocock.domain_doc(domain_text, map_exists)
        drift = parsed["glossary_drift"] + parsed["adr_drift"]
        doc = {"path": pocock.DOMAIN_DOC, "status": "drift" if drift else "ok",
               "detail": "; ".join(drift) if drift else "names the glossary and the ADR directories"}
    glossary = {"status": None, "files": [], "detail": ""}
    if parsed["glossary_drift"]:
        glossary.update(status="drift", detail="domain doc, %s" % "; ".join(parsed["glossary_drift"]))
    else:
        if parsed["names_map"] and map_exists:
            listed = pocock.glossary_map(read_head(head, pocock.GLOSSARY_MAP))
            glossary["map"] = pocock.GLOSSARY_MAP
            if not listed:
                glossary.update(status="drift", detail="%s, links no glossary file" % pocock.GLOSSARY_MAP)
        else:
            listed = [pocock.GLOSSARY]
        for rel in listed:
            text = read_head(head, rel)
            terms = pocock.glossary_terms(text) if text is not None else []
            glossary["files"].append({"path": rel, "found": text is not None, "terms": terms})
        present = [g for g in glossary["files"] if g["found"]]
        if glossary["status"] == "drift":
            pass
        elif not present:
            glossary.update(status="absent", detail="not created yet (Pocock creates it lazily)")
        elif not any(g["terms"] for g in present):
            glossary.update(status="drift", detail="%s, no `**Term**:` line" % ", ".join(g["path"] for g in present))
        else:
            glossary.update(status="ok", detail="%d term(s) in %s" % (
                sum(len(g["terms"]) for g in present), ", ".join(g["path"] for g in present)))
    adrs = {"status": None, "dirs": [], "changed": [], "detail": ""}
    if parsed["adr_drift"]:
        adrs.update(status="drift", detail="domain doc, %s" % "; ".join(parsed["adr_drift"]))
    else:
        wanted = [d for d in parsed["adr_dirs"] if "<" not in d]
        templates = [re.sub(r"<[^>]*>", "*", d) for d in parsed["adr_dirs"] if "<" in d]
        contexts = [os.path.dirname(g["path"]) for g in glossary["files"] if os.path.dirname(g["path"])]
        templates += ["%s/%s" % (c, pocock.DEFAULT_ADR_DIR) for c in contexts]
        if templates:
            for d in head_dirs(head):
                if any(fnmatch.fnmatchcase(d, t) for t in templates) and d not in wanted:
                    wanted.append(d)
        for d in wanted:
            full = os.path.join(head, d)
            files = sorted("%s/%s" % (d, n) for n in os.listdir(full)
                           if n.endswith(".md") and os.path.isfile(os.path.join(full, n))) if os.path.isdir(full) else []
            adrs["dirs"].append({"path": d, "files": files})
        adrs["changed"] = [{"path": c.path, "change": c.change} for c in ctx.changes
                           if any(c.path.startswith(d["path"] + "/") or c.old.startswith(d["path"] + "/")
                                  for d in adrs["dirs"])]
        count = sum(len(d["files"]) for d in adrs["dirs"])
        if count:
            adrs.update(status="ok", detail="%d ADR(s) in %s" % (
                count, ", ".join(d["path"] + "/" for d in adrs["dirs"] if d["files"])))
        else:
            adrs.update(status="absent", detail="no ADR in %s (Pocock creates them lazily)" % (
                ", ".join(d["path"] + "/" for d in adrs["dirs"]) or pocock.DEFAULT_ADR_DIR + "/"))
    return {"doc": doc, "glossary": glossary, "adrs": adrs}


# --- New terms ------------------------------------------------------------------------

TYPE_DEFS = {
    "py": r"^\s*class\s+(?P<name>[A-Za-z]\w*)",
    "js": r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:class|interface|type|enum)\s+"
          r"(?P<name>[A-Za-z_$][\w$]*)",
    "php": r"^\s*(?:(?:final|abstract|readonly)\s+)*(?:class|interface|trait|enum)\s+(?P<name>[A-Za-z_]\w*)",
    "rb": r"^\s*(?:class|module)\s+(?P<name>[A-Z]\w*)",
    "go": r"^\s*type\s+(?P<name>[A-Za-z]\w*)\b",
    "jvm": r"\b(?:class|interface|enum|record|struct|object)\s+(?P<name>[A-Z]\w*)",
    "rs": r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait|type)\s+(?P<name>[A-Za-z_]\w*)",
    "ex": r"^\s*defmodule\s+(?:[\w]+\.)*(?P<name>\w+)",
}
TYPE_RES = {k: re.compile(v) for k, v in TYPE_DEFS.items()}
# Words that say what kind of code a type is, not what it is about.
TECH = set("""
abstract adapter api app application base builder bundle cache client collection command component config
configuration context controller converter core dao data decorator default dispatcher dto emitter entity enum
error event exception extension factory fake fixture form formatter generator generic guard handler helper
helpers hook http i impl info input interface item items iterator job json kernel layout list listener loader
logger manager map mapper message middleware mock model module normalizer object observer options output page
params parser payload plugin presenter props provider proxy query queue record renderer repository request
resource response result route router schema serializer service services set settings spec sql state store
strategy struct stub subscriber task test tests trait transformer type types util utils validator value view
visitor vo voter widget worker wrapper xml
""".split())
WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def words(name):
    return [w.lower() for w in WORD.findall(name.replace("_", " ").replace("-", " "))]


def domain_words(name):
    """The words of a type name without the technical ones at either end
    (`AbstractInvoiceRepository` -> invoice)."""
    w = words(name)
    while w and w[0] in TECH:
        w = w[1:]
    while w and w[-1] in TECH:
        w = w[:-1]
    return w


def singular(ws):
    if ws and len(ws[-1]) > 3 and ws[-1].endswith("s") and not ws[-1].endswith("ss"):
        return ws[:-1] + [ws[-1][:-1]]
    return ws


def terms(ctx, glossary):
    """(rows, known): the type names the diff defines in code (tests left
    out) that no glossary term names, each `T<n>` with a `note` when the
    glossary says to avoid its words; and the ones a term names."""
    vocab, avoid = {}, {}
    for g in glossary.get("files") or []:
        for t in g.get("terms") or []:
            vocab[tuple(singular(words(t["term"])))] = (t["term"], g["path"], t["line"])
            for a in t.get("avoid") or []:
                avoid[tuple(singular(words(a)))] = t["term"]
    rows, known, seen = [], [], set()
    for c in ctx.changes:
        lang = detectors.LANG.get(os.path.splitext(c.path)[1].lstrip(".").lower())
        if not lang or detectors.is_test(c.path) or c.deleted:
            continue
        for n, text in c.added():
            m = TYPE_RES[lang].search(text)
            if not m or detectors.comment(text):
                continue
            name = m.group("name")
            dw = tuple(singular(domain_words(name)))
            if name in seen or not dw:
                continue
            seen.add(name)
            # Not new: the name, or its domain part (`Order` of
            # `OrderController`), is already in the repository at the base.
            # A word the glossary says to avoid is a row all the same.
            if dw in vocab:
                term, gpath, gline = vocab[dw]
                known.append({"path": c.path, "line": n, "name": name, "term": term, "glossary": "%s:%d" % (gpath, gline)})
                continue
            if dw not in avoid and (ctx.mentioned_at_base(name) or ctx.mentioned_at_base(
                    "".join(w.capitalize() for w in domain_words(name)))):
                continue
            row = {"tid": "T%d" % (len(rows) + 1), "path": c.path, "line": n, "name": name, "words": " ".join(dw)}
            if dw in avoid:
                row["note"] = "the glossary says to avoid `%s`: use **%s**" % (" ".join(dw), avoid[dw])
            rows.append(row)
    return rows, known


# --- The import graph, stack-neutral --------------------------------------------------

def module_edges(side):
    """{(module, module): [file edge]} of one side of a graph: the edges
    between files of two different modules."""
    mods = (side or {}).get("modules") or {}
    out = {}
    for e in (side or {}).get("edges") or []:
        a, b = mods.get(e.get("from")), mods.get(e.get("to"))
        if a and b and a != b:
            out.setdefault((a, b), []).append(e)
    return out


def components(pairs):
    """The strongly connected components of more than one module."""
    graph = {}
    for a, b in pairs:
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set())
    index, low, stack, on, out, counter = {}, {}, [], set(), [], [0]
    for root in sorted(graph):
        if root in index:
            continue
        work = [(root, iter(sorted(graph[root])))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            node, it = work[-1]
            nxt = next(it, None)
            if nxt is None:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == node:
                            break
                    if len(comp) > 1:
                        out.append(sorted(comp))
            elif nxt not in index:
                index[nxt] = low[nxt] = counter[0]
                counter[0] += 1
                stack.append(nxt)
                on.add(nxt)
                work.append((nxt, iter(sorted(graph[nxt]))))
            elif nxt in on:
                low[node] = min(low[node], index[nxt])
    return sorted(out)


def graph_diff(graph):
    """(new edges, new cycles) between modules, from a graph in the
    stack-neutral format: `{"base": side, "head": side}`, each side
    `{"modules": {path: module}, "edges": [{"from": path, "to": path,
    "line": n}]}`, the line in the importing file on that side.

    A new edge is a pair of modules the head imports in that direction and
    the base did not, with the file edges that make it (`via`). A new cycle
    is a group of modules that import each other at the head, not contained
    in a cycle of the base."""
    graph = graph or {}
    base, head = module_edges(graph.get("base")), module_edges(graph.get("head"))
    new = [{"from": a, "to": b, "via": head[(a, b)][:5]} for a, b in sorted(head) if (a, b) not in base]
    base_cycles = [set(c) for c in components(base)]
    cycles = []
    for comp in components(head):
        if any(set(comp) <= b for b in base_cycles):
            continue
        inner = [e for e in new if e["from"] in comp and e["to"] in comp]
        via = [v for e in inner for v in e["via"][:1]] or [head[p][0] for p in sorted(head)
                                                            if p[0] in comp and p[1] in comp][:1]
        cycles.append({"modules": comp, "via": via})
    return new, cycles


def graph_output(name, version, graph, stack, tool=None, heuristic=True, content=False, applies=(),
                 covered=(), not_covered=(), gaps=()):
    """The output a stack adapter writes for its import graph: the graph in
    the stack-neutral format, the new edges and cycles, and a signal on the
    importing file of each. `name` starts with `import-graph`."""
    if not name.startswith(GRAPH_PREFIX):
        raise ValueError("an import graph output is named %s-<stack>" % GRAPH_PREFIX)
    new, cycles = graph_diff(graph)
    signals = []
    for e in new:
        v = e["via"][0]
        signals.append(detectors.signal(v["from"], "import-edge-added", "new import from module `%s` to module `%s`"
                                        " (`%s`)" % (e["from"], e["to"], v["to"]), v.get("line")))
    for c in cycles:
        if c["via"]:
            v = c["via"][0]
            signals.append(detectors.signal(v["from"], "import-cycle-added", "new cycle between modules %s"
                                            % ", ".join("`%s`" % m for m in c["modules"]), v.get("line")))
    return detectors.output(name, version, content, list(applies), list(covered), list(not_covered), signals,
                            tool=tool, heuristic=heuristic, gaps=gaps, stack=stack, graph=graph,
                            new_edges=new, new_cycles=cycles)


def graph_outputs(outputs):
    """[(rel, output)] of the import graph outputs among [(rel, output)]."""
    return [(rel, o) for rel, o in outputs if isinstance(o, dict) and isinstance(o.get("graph"), dict)
            and str(o.get("detector", "")).startswith(GRAPH_PREFIX)]


def import_rows(outputs):
    """[{gid, detector, path, line, what}]: each new edge, then each new
    cycle, of every import graph output, in order."""
    out = []
    for rel, o in graph_outputs(outputs):
        new, cycles = graph_diff(o["graph"])
        name = o.get("detector") or rel
        for e in new:
            v = e["via"][0]
            out.append({"gid": "G%d" % (len(out) + 1), "detector": name, "path": v["from"], "line": v.get("line"),
                        "what": "edge `%s` -> `%s`" % (e["from"], e["to"])})
        for c in cycles:
            v = c["via"][0] if c["via"] else {"from": "", "line": None}
            out.append({"gid": "G%d" % (len(out) + 1), "detector": name, "path": v["from"], "line": v.get("line"),
                        "what": "cycle %s" % ", ".join("`%s`" % m for m in c["modules"])})
    return out


# --- The detector ------------------------------------------------------------------------

def fixed_areas(dom, graphs):
    """{area: status} for the areas whose status is fixed by what exists."""
    out = {}
    if not graphs:
        out["Import graph"] = "not-evaluable (%s)" % NO_GRAPH
    for area, part, absent in (("Glossary", dom["glossary"], NO_GLOSSARY), ("ADRs", dom["adrs"], NO_ADRS)):
        if part["status"] == "absent":
            out[area] = "not-evaluable (%s)" % absent
        elif part["status"] == "drift":
            out[area] = "not-evaluable (contract drift: %s)" % part["detail"]
    return out


def detect(ctx, version, base_dirs, domain_text, outputs):
    """The `structure` output. `base_dirs`: the directories at the merge
    base; `domain_text`: the domain doc at the base, None when missing;
    `outputs`: the other detectors' [(name, output)]."""
    dom = domain(ctx, domain_text)
    files = new_files(ctx, base_dirs)
    rows, known = terms(ctx, dom["glossary"]) if dom["glossary"]["status"] == "ok" else ([], [])
    graphs = graph_outputs(outputs)
    return detectors.output(
        DETECTOR, version, False, [], [f["path"] for f in files], [], [], heuristic=True,
        new_files=files, new_modules=sorted({f["module"] for f in files if f["new_module"]}),
        dependencies=dependencies(ctx), domain=dom, terms=rows, known_terms=known,
        import_graphs=[name for name, _ in graphs], areas=fixed_areas(dom, graphs))


def structure_output(outputs):
    return next((o for _, o in outputs if isinstance(o, dict) and o.get("detector") == DETECTOR), None)


# --- The worksheet ----------------------------------------------------------------------------

def where(path, line):
    return "`%s:%d`" % (path, line) if line else "`%s`" % path


def dependency_cell(d):
    what = "`%s` %s" % (d["name"], intent.cell(d["spec"]))
    if d.get("category"):
        what += ", %s" % d["category"]
        if d.get("peers"):
            what += ", beside %s" % ", ".join("`%s`" % p for p in d["peers"])
    return "%s %s %s" % (d["did"], where(d["path"], d.get("line")), what)


def term_cell(t):
    cell = "%s %s `%s`" % (t["tid"], where(t["path"], t["line"]), t["name"])
    return cell + (": %s" % t["note"] if t.get("note") else "")


def import_cell(r):
    return "%s %s %s %s" % (r["gid"], where(r["path"], r.get("line")), r["detector"], r["what"])


def worksheet(outputs, version):
    """The structure findings file before the step runs: one row per new
    dependency, candidate term and import change, `?` where it judges; the
    areas fixed by what exists already set."""
    so = structure_output(outputs) or {}
    fixed = so.get("areas") or {}
    rows = []
    for area in AREAS:
        if area in fixed:
            rows.append("| %s | %s | Fixed by the run: %s. |" % (area, intent.cell(fixed[area]), area_note(area, so)))
        else:
            rows.append("| %s | not-evaluable | Step not run yet: run %s. |" % (area, STEP_FILE))
    out = ["# Structure", "", "## Coverage", "", "skill: %s, tools: []" % version, "",
           "| Area | Status | Notes |", "|---|---|---|"] + rows + [
           "", "Axis: not-evaluable (%s)" % NOT_RUN_YET, ""]
    deps, terms_, imports = so.get("dependencies") or [], so.get("terms") or [], import_rows(outputs)
    out += ["## Dependencies", ""]
    if deps:
        out += ["| Dependency | Needed | Why | Finding |", "|---|---|---|---|"]
        out += ["| %s | %s | %s | |" % (dependency_cell(d), UNFILLED, UNFILLED) for d in deps]
    else:
        out.append("None.")
    out += ["", "## Terms", ""]
    if terms_:
        out += ["| Term | Judgment | Finding |", "|---|---|---|"]
        out += ["| %s | %s | |" % (intent.cell(term_cell(t)), UNFILLED) for t in terms_]
    else:
        out.append("None.")
    out += ["", "## Imports", ""]
    if imports:
        out += ["| Import | Judgment | Finding |", "|---|---|---|"]
        out += ["| %s | %s | |" % (intent.cell(import_cell(r)), UNFILLED) for r in imports]
    else:
        out.append("None.")
    out += ["", "## Findings", "", "None.", "", "## Leads", "", "None.", ""]
    return "\n".join(out)


def area_note(area, so):
    dom = so.get("domain") or {}
    if area == "Import graph":
        return "no stack adapter graphs this diff's code: PHP, TypeScript, JavaScript and Python have one"
    part = dom.get("glossary" if area == "Glossary" else "adrs") or {}
    return intent.cell(part.get("detail") or "")


# --- Reading the tables -------------------------------------------------------------------------

def read_file(path):
    """{sections, areas, dependencies, terms, imports} of a structure findings file."""
    lines = read(path)
    secs = {name: items for name, _, items in blocks(lines, 2)[1:]}
    out = {"sections": [n for n in secs if n in SECTIONS], "areas": {}, "dependencies": [], "terms": [],
           "imports": []}
    for line, cells in intent.table(secs.get("Coverage", [])):
        if len(cells) >= 2:
            out["areas"][cells[0]] = (line, " ".join(cells[1].split()))
    for line, cells in intent.table(secs.get("Dependencies", [])):
        cells += [""] * (4 - len(cells))
        out["dependencies"].append({"line": line, "id": row_id(cells[0]), "cell": cells[0],
                                    "judgment": cells[1].strip().lower(), "why": cells[2].strip(),
                                    "findings": FID.findall(cells[3])})
    for name, key in (("Terms", "terms"), ("Imports", "imports")):
        for line, cells in intent.table(secs.get(name, [])):
            cells += [""] * (3 - len(cells))
            out[key].append({"line": line, "id": row_id(cells[0]), "cell": cells[0],
                             "judgment": cells[1].strip().lower(), "findings": FID.findall(cells[2])})
    return out


def row_id(cell):
    m = ROW_ID.match(cell)
    return "%s%s" % (m.group(1), m.group(2)) if m else cell


def summary_line(it, so):
    so = so or {}
    files = so.get("new_files") or []
    mods = so.get("new_modules") or []
    not_needed = sum(1 for r in it["dependencies"] if r["judgment"] == "not needed")
    domain_ = sum(1 for r in it["terms"] if r["judgment"] == "domain term")
    boundary = sum(1 for r in it["imports"] if r["judgment"] == "boundary")
    graph = ("%d import change(s), %d across a boundary" % (len(it["imports"]), boundary)
             if so.get("import_graphs") else "import graph not evaluable")
    return ("Structure: %d new file(s), %d new module(s); %d new dependency(ies), %d not needed; %d new type"
            " name(s) outside the glossary, %d judged a domain term; %s." % (
                len(files), len(mods), len(it["dependencies"]), not_needed, len(it["terms"]), domain_, graph))


# --- The validator's checks ----------------------------------------------------------------------------

class Check:
    """The structure file checked against the run: `error(line, message)` and
    `pending(line, message)` report on the structure findings file.
    `findings` maps each finding ID of this file to its line."""

    def __init__(self, outputs, findings, error, pending):
        self.outputs, self.findings = outputs, findings
        self.so = structure_output(outputs)
        self.error, self.pending = error, pending

    def run(self, path, axis_status):
        status, why = axis_status
        if status == "not-evaluable" and why == NOT_RUN_YET:
            self.pending(None, "the structure step has not run on this run directory: run %s" % STEP_FILE)
            return None
        if status not in ("evaluated", "partial") or self.so is None:
            return None
        it = read_file(path)
        for name in SECTIONS:
            if name not in it["sections"]:
                self.error(None, "section `## %s` missing: an evaluated structure step fills it" % name)
        self.check_areas(it)
        self.check_rows(it["dependencies"], [(d["did"], d["path"]) for d in self.so.get("dependencies") or []],
                        "Dependencies", NEEDED, "not needed")
        for row in it["dependencies"]:
            if row["judgment"] in NEEDED and (not row["why"] or row["why"] == UNFILLED):
                self.error(row["line"], "%s: say why it looks %s" % (row["id"], row["judgment"]))
        self.check_rows(it["terms"], [(t["tid"], t["path"]) for t in self.so.get("terms") or []],
                        "Terms", TERM_JUDGMENTS, "domain term")
        self.check_rows(it["imports"], [(r["gid"], r["path"]) for r in import_rows(self.outputs)],
                        "Imports", IMPORT_JUDGMENTS, "boundary")
        return it

    def check_areas(self, it):
        fixed = self.so.get("areas") or {}
        for area in AREAS:
            if area not in it["areas"]:
                self.error(None, "coverage area `%s` missing" % area)
                continue
            line, status = it["areas"][area]
            if area in fixed and status != fixed[area]:
                self.error(line, "area `%s` is `%s` in this run, fixed by what exists: not `%s`"
                           % (area, fixed[area], status))
            elif area not in fixed and status.startswith("not-evaluable"):
                self.error(line, "area `%s` is evaluable in this run: judge it, or say `partial (<what>)`" % area)

    def check_rows(self, rows, expected, section, judgments, needs_finding):
        want = dict(expected)
        seen = {}
        for row in rows:
            line, rid = row["line"], row["id"]
            if rid in seen:
                self.error(line, "%s has two rows (also line %d)" % (rid, seen[rid]))
            seen.setdefault(rid, line)
            if rid not in want:
                self.error(line, "%s is not a row of `## %s` in this run" % (rid, section))
            elif want[rid] and "`%s" % want[rid] not in row["cell"]:
                self.error(line, "%s is about `%s`, not what this row names" % (rid, want[rid]))
            if row["judgment"] == UNFILLED:
                self.error(line, "%s: judgment left `?`" % rid)
                continue
            if row["judgment"] not in judgments:
                self.error(line, "%s: judgment `%s` not in %s" % (rid, row["judgment"], " | ".join(judgments)))
                continue
            if row["judgment"] == needs_finding and not row["findings"]:
                self.error(line, "%s (%s) needs the finding that says why" % (rid, row["judgment"]))
            for fid in row["findings"]:
                if fid not in self.findings:
                    self.error(line, "%s cites %s, which is not a finding of this file" % (rid, fid))
        for rid in want:
            if rid not in seen:
                self.error(None, "%s has no row in `## %s`" % (rid, section))


# --- The brief ------------------------------------------------------------------------------------------

def brief_lines(so, it, outputs):
    """The brief's New structure section: new files by class, new modules,
    new dependencies, the import graph, the glossary and the ADRs. `it` is
    the step's tables when it ran, None otherwise."""
    if so is None:
        return ["Not looked at: this run has no structure detector output."]
    out = []
    files = so.get("new_files") or []
    mods = so.get("new_modules") or []
    if mods:
        out.append("- New modules: %s." % ", ".join(
            "`%s/` (%d file(s))" % (m, sum(1 for f in files if f["module"] == m)) for m in mods))
    for cls in STRUCTURAL:
        of = [f for f in files if f["class"] == cls]
        if of:
            out.append("- %s: %s." % (cls[0].upper() + cls[1:], ", ".join(
                "`%s`%s" % (f["path"], " (from `%s`)" % f["from"] if f.get("from") else "") for f in of)))
    rest = {cls: sum(1 for f in files if f["class"] == cls) for cls in ("source", "other")}
    if not files:
        out.append("- No new file.")
    elif rest["source"] or rest["other"]:
        out.append("- Also %d new code file(s) in existing modules and %d other new file(s)." % (
            rest["source"], rest["other"]))
    judged = {r["id"]: r for r in (it or {}).get("dependencies") or []}
    for d in so.get("dependencies") or []:
        r = judged.get(d["did"])
        if r and r["judgment"] in NEEDED:
            verdict = "%s: %s%s" % (r["judgment"], r["why"].rstrip("."),
                                    " (%s)" % ", ".join(r["findings"]) if r["findings"] else "")
        else:
            verdict = "not judged: the structure step did not run"
        out.append("- New dependency %s: %s." % (dependency_cell(d).split(" ", 1)[1], verdict))
    graphs = graph_outputs(outputs)
    if not graphs:
        out.append("- Import graph: not-evaluable (%s)." % NO_GRAPH)
    for rel, o in graphs:
        new, cycles = graph_diff(o["graph"])
        how = o.get("tool") or ("heuristic" if o.get("heuristic") else "")
        out.append("- Import graph (%s%s): %d new cross-module edge(s), %d new cycle(s)." % (
            rel, ", %s" % how if how else "", len(new), len(cycles)))
    dom = so.get("domain") or {}
    areas = so.get("areas") or {}
    terms_ = {r["id"]: r for r in (it or {}).get("terms") or []}
    g = dom.get("glossary") or {}
    if "Glossary" in areas:
        out.append("- Glossary: %s." % areas["Glossary"])
    else:
        rows = so.get("terms") or []
        missing = [r for r in terms_.values() if r["judgment"] == "domain term"]
        line = "- Glossary: %s; %d new type name(s) no term names" % (g.get("detail"), len(rows))
        if it is not None:
            line += ", %d judged a domain term%s" % (len(missing), " (%s)" % ", ".join(
                sorted({f for r in missing for f in r["findings"]})) if missing else "")
        out.append(line + ".")
    a = dom.get("adrs") or {}
    if "ADRs" in areas:
        out.append("- ADRs: %s." % areas["ADRs"])
    else:
        changed = a.get("changed") or []
        out.append("- ADRs: %s%s." % (a.get("detail"), "; this diff %s" % ", ".join(
            "%s `%s`" % ({"added": "adds", "deleted": "deletes", "renamed": "renames"}.get(c["change"], "changes"),
                         c["path"]) for c in changed) if changed else ""))
    return out
