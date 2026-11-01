#!/usr/bin/env python3
"""Check that the pointers of an audit workspace open, and that each quote is
at its line, in the findings files, the codebase map and the plan. Read-only.

Usage: python3 -I check-pointers.py <workspace> [--repo <path>]

Quotes are checked in the findings files only: the map's pointers need none,
and the plan's quotes are not quotes of the code. A pointer is `path:line` or `path:start-end`, relative to the working copy
(`working_copy:` in the engagement, or --repo), the dependency installs the
map names or the workspace (a bare file name: anywhere under tool-output/ or
client-docs/); `<short sha>:path:line` reads <workspace>/repo-<short sha>/.
Prints one line per problem, then a summary:
  MISMATCH    the quote is not at its line (says where it is, if anywhere)
  MISSING     the file does not exist, or the line is past its end
  UNRESOLVED  looks like a file name without a directory, found nowhere: read it
Whether the line proves what the text says stays with the step that owns it.
Exit status: 0 none of the first two, 1 some, 2 the workspace cannot be read.
Python 3.8 or later, standard library only.
"""
import glob
import os
import re
import sys

VERSION = "finding-format@0.26.0"

POINTER = re.compile(r"(?<![\w/.:@~$-])(?:(?P<sha>[0-9a-f]{7,40}):)?"
                     r"(?P<path>[\w@+~.-]+(?:/[\w@+~.\[\]()-]+)*):"
                     r"(?P<start>\d+)(?:-(?P<end>\d+))?(?::\d+)?(?![\w/]|\.\w)")
QUOTE = re.compile(r"[`*]*\s*(?:[:,—–-]\s*)?(?:\"(?P<a>[^\"]+)\"|“(?P<b>[^”]+)”|«(?P<c>[^»]+)»)")
ELISION = re.compile(r"\[?…\]?|\[\.\.\.\]|\.\.\.|<redacted>")


def norm(text):
    return " ".join(text.split())


def pieces(quote):
    parts = [norm(p).strip("`*").strip() for p in ELISION.split(quote.replace('\\"', '"').replace("\\|", "|"))]
    return [p for p in parts if len(p) >= 3]


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().split("\n")


def field(path, name):
    if os.path.exists(path):
        for line in read_lines(path):
            m = re.match(r"^%s:\s*(\S.*)$" % name, line.strip())
            if m:
                return m.group(1).strip()
    return None


def roots_of(root, repo):
    """Where a relative pointer may open, in order."""
    roots = []
    copy = repo or field(os.path.join(root, "00-engagement.md"), "working_copy")
    if copy:
        copy = os.path.expanduser(copy)
        roots.append(copy if os.path.isabs(copy) else os.path.join(root, copy))
    map_path = os.path.join(root, "01-codebase-map.md")
    if os.path.exists(map_path):
        for line in read_lines(map_path)[:20]:
            for token in re.findall(r"[\w./~-]*(?:node_modules|vendor)\b", line):
                token = os.path.expanduser(token)
                for base in ([token] if os.path.isabs(token) else [os.path.join(root, token)] + [os.path.join(r, token) for r in roots]):
                    if os.path.isdir(base):
                        roots.append(os.path.dirname(os.path.normpath(base)))
    roots.append(root)
    return list(dict.fromkeys(os.path.normpath(r) for r in roots))


def workspace_files(root):
    """Bare file name -> paths, under the folders a step keeps its copies in."""
    names = {}
    for folder in ("tool-output", "client-docs"):
        for base, _, files in os.walk(os.path.join(root, folder)):
            for name in files:
                names.setdefault(name, []).append(os.path.join(base, name))
    return names


def resolve(path, sha, root, roots, names):
    if sha:
        for clone in sorted(glob.glob(os.path.join(root, "repo-*"))):
            name = os.path.basename(clone)[5:]
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


def scan(path, root, roots, names, quotes, out, counts):
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
        found = resolve(target, m.group("sha"), root, roots, names)
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


def main(argv):
    args = argv[1:]
    root, repo = None, None
    while args:
        a = args.pop(0)
        if a == "--repo" and args:
            repo = args.pop(0)
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        elif a == "--version":
            print(VERSION)
            return 0
        elif root is None and not a.startswith("-"):
            root = a
        else:
            print("unknown argument: %s" % a, file=sys.stderr)
            return 2
    if root is None:
        print(__doc__, file=sys.stderr)
        return 2
    files = sorted(glob.glob(os.path.join(root, "findings", "*.md")))
    if not files:
        print("no findings file in %s" % root, file=sys.stderr)
        return 2
    for name in ("01-codebase-map.md", "02-remediation-plan.md"):
        if os.path.exists(os.path.join(root, name)):
            files.append(os.path.join(root, name))
    roots = roots_of(root, repo)
    names = workspace_files(root)
    findings_dir = os.path.join(root, "findings")
    out, counts = [], {"pointers": 0, "quotes": 0, "MISMATCH": 0, "MISSING": 0, "UNRESOLVED": 0}
    for path in files:
        scan(path, root, roots, names, os.path.dirname(path) == findings_dir, out, counts)
    for line in out:
        print(line)
    print("%s: %d pointers opened in %d files, %d with a quote; looked in: %s" % (
        VERSION, counts["pointers"], len(files), counts["quotes"], ", ".join(os.path.relpath(r, root) for r in roots)))
    print("mismatch %d, missing %d, unresolved %d" % (counts["MISMATCH"], counts["MISSING"], counts["UNRESOLVED"]))
    failed = counts["MISMATCH"] or counts["MISSING"]
    print("RESULT: %s" % ("FAIL" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
