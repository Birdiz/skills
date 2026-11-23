#!/usr/bin/env python3
"""Copy the finding core (`core/` at the repository root) into every plugin
the marketplace lists, so that each installed plugin carries its own copy.

Usage: python3 -I tools/sync_core.py [--check] [--root <repository>]

Without --check, each plugin's `core/` is made identical to the source:
changed and missing files are written, files the source no longer has are
removed. With --check, nothing is written: every difference is printed and
the exit status is 1. Edit the core at the repository root only; a copy
edited in place is a drift that --check reports.

Exit status: 0 in sync (or synced), 1 drift found by --check, 2 the
repository cannot be read.
Python 3.8 or later, standard library only.
"""
import argparse
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True

CORE = "core"
MARKETPLACE = os.path.join(".claude-plugin", "marketplace.json")
IGNORED_DIRS = {"__pycache__"}
IGNORED_FILES = {".DS_Store"}


class RepoError(Exception):
    pass


def files_under(top):
    """Relative paths of the files under `top`, caches and OS litter left out."""
    found = set()
    for d, dirs, files in os.walk(top):
        dirs[:] = sorted(x for x in dirs if x not in IGNORED_DIRS)
        for f in files:
            if f in IGNORED_FILES or f.endswith(".pyc"):
                continue
            found.add(os.path.relpath(os.path.join(d, f), top).replace(os.sep, "/"))
    return found


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def plugin_dirs(root):
    """The directory of every plugin in the marketplace, relative to `root`."""
    path = os.path.join(root, MARKETPLACE)
    try:
        with open(path, encoding="utf-8") as fh:
            plugins = json.load(fh)["plugins"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise RepoError("cannot read the plugins of %s: %s" % (MARKETPLACE, e))
    dirs = []
    for plugin in plugins:
        source = plugin.get("source") if isinstance(plugin, dict) else None
        name = plugin.get("name", "?") if isinstance(plugin, dict) else "?"
        if not isinstance(source, str):
            raise RepoError("plugin %s: its source is not a directory of this repository" % name)
        rel = os.path.normpath(source)
        if rel == "." or rel.startswith("..") or os.path.isabs(rel):
            raise RepoError("plugin %s: source %r must be its own directory inside the repository"
                            % (name, source))
        if not os.path.isdir(os.path.join(root, rel)):
            raise RepoError("plugin %s: source %s does not exist" % (name, source))
        dirs.append(rel.replace(os.sep, "/"))
    if not dirs:
        raise RepoError("%s lists no plugin" % MARKETPLACE)
    return dirs


def drift(source, copy):
    """(relative path, problem) for every way `copy` differs from `source`."""
    want = files_under(source)
    have = files_under(copy) if os.path.isdir(copy) else set()
    problems = []
    for rel in sorted(want | have):
        if rel not in have:
            problems.append((rel, "missing"))
        elif rel not in want:
            problems.append((rel, "not in the source"))
        elif read_bytes(os.path.join(source, rel)) != read_bytes(os.path.join(copy, rel)):
            problems.append((rel, "differs from the source"))
    return problems


def sync(source, copy):
    """Make `copy` identical to `source`; return the number of files touched."""
    touched = 0
    for rel, problem in drift(source, copy):
        dest = os.path.join(copy, rel)
        if problem == "not in the source":
            os.remove(dest)
        else:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(source, rel), dest)
        touched += 1
    for d, dirs, files in os.walk(copy, topdown=False):
        if d != copy and not os.listdir(d):
            os.rmdir(d)
    return touched


def main(argv):
    parser = argparse.ArgumentParser(prog=os.path.basename(argv[0]),
                                     description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if a plugin's copy differs from the source")
    parser.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        help="the repository (default: the one holding this script)")
    args = parser.parse_args(argv[1:])
    root = os.path.abspath(args.root)
    source = os.path.join(root, CORE)
    try:
        if not files_under(source):
            raise RepoError("no core at %s" % source)
        plugins = plugin_dirs(root)
    except RepoError as e:
        print("ERROR    %s" % e)
        return 2
    drifted = 0
    for plugin in plugins:
        copy = os.path.join(root, plugin, CORE)
        if args.check:
            problems = drift(source, copy)
            for rel, problem in problems:
                print("DRIFT    %s/%s/%s: %s" % (plugin, CORE, rel, problem))
            drifted += bool(problems)
        else:
            touched = sync(source, copy)
            print("%s/%s: %s" % (plugin, CORE, "%d file(s) updated" % touched if touched else "up to date"))
    if args.check:
        if drifted:
            print("%d plugin(s) out of sync with %s/: run python3 -I tools/sync_core.py" % (drifted, CORE))
            return 1
        print("%s/ in sync in %d plugin(s): %s" % (CORE, len(plugins), ", ".join(plugins)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
