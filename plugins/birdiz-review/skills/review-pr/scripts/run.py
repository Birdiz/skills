#!/usr/bin/env python3
"""Start a review run on a branch or a range: resolve it, refuse an empty
diff, detect the tools, run the detectors, write the run directory and its
brief. Never writes to the reviewed repository.

Usage: python3 -I run.py <branch | base..head> [--repo <path>]

A branch is compared with the remote's default branch (else `main`, else
`master`); a range `base..head` (or `base...head`) with its base. Either
way the diff runs from the merge base to the head, read from git objects:
nothing is checked out, the working copy is never read or written.
The run directory is
  $XDG_STATE_HOME/birdiz-review/runs/<repo>/<branch>/<head short sha>/
(~/.local/state when XDG_STATE_HOME is unset), with `/` and other
characters escaped in <repo> and <branch>. A run on a head that already
has one replaces it: same head, same round.
Prints a summary, then `RUN: <run directory>` as its last line.
Exit status: 0 run written, 2 refused (empty diff, unknown ref, not a
repository): nothing written.
Python 3.8 or later, standard library only.
"""
import os
import sys

sys.dont_write_bytecode = True  # leave no __pycache__ in the plugin


def _paths():
    """This directory (the review extension) and the plugin's copy of the
    finding core, the nearest `core/finding_core/` above it, never past the
    plugin's root (`.claude-plugin/plugin.json`): `python3 -I` puts neither
    on the path from Python 3.11 on."""
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    while not os.path.isfile(os.path.join(d, "core", "finding_core", "__init__.py")):
        if (os.path.isfile(os.path.join(d, ".claude-plugin", "plugin.json"))
                or os.path.dirname(d) == d):
            sys.exit("finding core not found above %s" % here)
        d = os.path.dirname(d)
    return [here, os.path.join(d, "core")]


for _p in reversed(_paths()):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from finding_core import NAME  # noqa: E402
import review_format as fmt  # noqa: E402
import review_run  # noqa: E402


def main(argv):
    args = argv[1:]
    repo, target = ".", None
    while args:
        a = args.pop(0)
        if a == "--repo" and args:
            repo = args.pop(0)
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        elif a == "--version":
            print("%s (%s)" % (fmt.VERSION, NAME))
            return 0
        elif target is None and not a.startswith("-"):
            target = a
        else:
            print("unknown argument: %s" % a, file=sys.stderr)
            return 2
    if target is None:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        root, run = review_run.start(repo, target)
    except review_run.Refused as e:
        print("REFUSED: %s" % e, file=sys.stderr)
        return 2
    h = run.header
    found = ["%s %s" % (t["name"], t["version"]) for t in h["tools"] if t["found"]]
    absent = [t["name"] for t in h["tools"] if not t["found"]]
    print("%s (%s): %s %s, diff %s (%s), %d changed files, round %d"
          % (fmt.VERSION, NAME, h["repo"], h["branch"], h["diff"], h["target"],
             len(run.changed()), fmt.rounds(root)))
    print("tools found: %s; not found: %s" % (", ".join(found) or "none", ", ".join(absent) or "none"))
    with open(os.path.join(root, fmt.BRIEF), encoding="utf-8") as fh:
        verdict = [line for line in fh.read().split("\n") if line.startswith("Proposed verdict:")]
    print(verdict[0] if verdict else "no verdict line")
    print("RUN: %s" % root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
