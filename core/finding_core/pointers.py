"""The pointer and quote check: each pointer opens, each quote is at its line.

A pointer is `path:line` or `path:start-end`, optionally `<short sha>:path:line`
for a later commit. Where a pointer may open (the roots, the folders a bare
file name is looked up in, the clones of later commits) and which files are
read is the workspace layout a plugin's `Layout` supplies.
"""
import glob
import os
import re
import sys

from . import NAME

POINTER = re.compile(r"(?<![\w/.:@~$-])(?:(?P<sha>[0-9a-f]{7,40}):)?"
                     r"(?P<path>[\w@+~.-]+(?:/[\w@+~.\[\]()-]+)*):"
                     r"(?P<start>\d+)(?:-(?P<end>\d+))?(?::\d+)?(?![\w/]|\.\w)")
QUOTE = re.compile(r"[`*]*\s*(?:[:,—–-]\s*)?(?:\"(?P<a>[^\"]+)\"|“(?P<b>[^”]+)”|«(?P<c>[^»]+)»)")
ELISION = re.compile(r"\[?…\]?|\[\.\.\.\]|\.\.\.|<redacted>")


class Layout:
    """Where a plugin's workspace keeps what pointers open. One instance per run."""

    name = "finding-core"   # the plugin's schema, with its version
    empty = "no findings file in %s"
    folders = ()            # workspace folders a bare file name is looked up in
    clones = "repo-"        # `<clones><short sha>/` holds a later commit

    def __init__(self, root, repo):
        self.root, self.repo = root, repo

    @classmethod
    def label(cls):
        return "%s (%s)" % (cls.name, NAME)

    def files(self):
        """The files to read, in order; empty when there is nothing to check."""
        return []

    def quoted(self, path):
        """Whether quotes after this file's pointers are checked."""
        return True

    def roots(self):
        """Where a relative pointer may open, in order."""
        return [self.root]


def norm(text):
    return " ".join(text.split())


def pieces(quote):
    parts = [norm(p).strip("`*").strip() for p in ELISION.split(quote.replace('\\"', '"').replace("\\|", "|"))]
    return [p for p in parts if len(p) >= 3]


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().split("\n")


def field(path, name):
    """The value of the first `<name>: <value>` line of a file, or None."""
    if os.path.exists(path):
        for line in read_lines(path):
            m = re.match(r"^%s:\s*(\S.*)$" % name, line.strip())
            if m:
                return m.group(1).strip()
    return None


def workspace_files(root, folders):
    """Bare file name -> paths, under the folders a step keeps its copies in."""
    names = {}
    for folder in folders:
        for base, _, files in os.walk(os.path.join(root, folder)):
            for name in files:
                names.setdefault(name, []).append(os.path.join(base, name))
    return names


def resolve(path, sha, root, roots, names, clones):
    if sha:
        for clone in sorted(glob.glob(os.path.join(root, clones + "*"))):
            name = os.path.basename(clone)[len(clones):]
            if name.startswith(sha) or sha.startswith(name):
                candidate = os.path.join(clone, path)
                return candidate if os.path.isfile(candidate) else None
    for base in roots:
        candidate = os.path.join(base, path)
        if os.path.isfile(candidate):
            return candidate
    hits = names.get(path, []) if "/" not in path else []
    return hits[0] if len(hits) == 1 else None


def check_quote(lines, start, end, quote):
    """Returns None when every piece of the quote is at its place, else where
    the first missing one is found ("line N") or "nowhere in the file"."""
    pointed = norm(" ".join(lines[start - 1:end]))
    window = norm(" ".join(lines[start - 1:end + 3]))
    parts = pieces(quote)
    for k, part in enumerate(parts):
        at = window.find(part)
        if at >= 0 and (k > 0 or at < max(len(pointed), 1)):
            continue
        for n, line in enumerate(lines, 1):
            if part in norm(line):
                return "line %d" % n
        return "nowhere in the file"
    return None


def scan(path, root, roots, names, quotes, out, counts, clones="repo-"):
    text = "\n".join(read_lines(path))
    where = os.path.relpath(path, root)
    for m in POINTER.finditer(text):
        target = m.group("path")
        if "..." in target or target.startswith("."):
            continue
        slash = "/" in target
        if not slash and not re.search(r"[A-Za-z]", target):
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        found = resolve(target, m.group("sha"), root, roots, names, clones)
        if found is None:
            if slash:
                counts["MISSING"] += 1
                out.append("MISSING    %s:%d  %s: no such file" % (where, line_no, m.group(0)))
            elif re.fullmatch(r"[\w-]*[A-Za-z][\w-]*\.[A-Za-z]\w*", target) and not re.search(r"\.(com|org|net|fr|io|dev|app|local|localhost)$", target):
                counts["UNRESOLVED"] += 1
                out.append("UNRESOLVED %s:%d  %s: found nowhere" % (where, line_no, m.group(0)))
            continue
        lines = read_lines(found)
        start = int(m.group("start"))
        end = int(m.group("end") or start)
        counts["pointers"] += 1
        if start < 1 or end > len(lines) or end < start:
            counts["MISSING"] += 1
            out.append("MISSING    %s:%d  %s: the file has %d lines" % (where, line_no, m.group(0), len(lines)))
            continue
        q = QUOTE.match(text, m.end()) if quotes else None
        if not q:
            continue
        counts["quotes"] += 1
        quote = q.group("a") or q.group("b") or q.group("c")
        problem = check_quote(lines, start, end, quote)
        if problem:
            counts["MISMATCH"] += 1
            out.append("MISMATCH   %s:%d  %s \"%s\": %s" % (where, line_no, m.group(0), norm(quote)[:60], problem))


def main(argv, layout, doc):
    """The pointer checker's command line, for a plugin's `Layout` class;
    `doc` is the usage --help prints."""
    args = argv[1:]
    root, repo = None, None
    while args:
        a = args.pop(0)
        if a == "--repo" and args:
            repo = args.pop(0)
        elif a in ("-h", "--help"):
            print(doc)
            return 0
        elif a == "--version":
            print(layout.label())
            return 0
        elif root is None and not a.startswith("-"):
            root = a
        else:
            print("unknown argument: %s" % a, file=sys.stderr)
            return 2
    if root is None:
        print(doc, file=sys.stderr)
        return 2
    lay = layout(root, repo)
    files = lay.files()
    if not files:
        print(lay.empty % root, file=sys.stderr)
        return 2
    roots = lay.roots()
    names = workspace_files(root, lay.folders)
    out, counts = [], {"pointers": 0, "quotes": 0, "MISMATCH": 0, "MISSING": 0, "UNRESOLVED": 0}
    for path in files:
        scan(path, root, roots, names, lay.quoted(path), out, counts, lay.clones)
    for line in out:
        print(line)
    print("%s: %d pointers opened in %d files, %d with a quote; looked in: %s" % (
        lay.label(), counts["pointers"], len(files), counts["quotes"], ", ".join(os.path.relpath(r, root) for r in roots)))
    print("mismatch %d, missing %d, unresolved %d" % (counts["MISMATCH"], counts["MISSING"], counts["UNRESOLVED"]))
    failed = counts["MISMATCH"] or counts["MISSING"]
    print("RESULT: %s" % ("FAIL" if failed else "OK"))
    return 1 if failed else 0
