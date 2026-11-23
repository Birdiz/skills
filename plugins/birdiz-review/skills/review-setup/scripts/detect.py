#!/usr/bin/env python3
"""Detect what review-setup proposes for a repository. Read-only.

Usage: python3 -I detect.py <repo> [--json] [--no-gh]

Reports the stacks, the detector tools this machine has (not stored
anywhere), the Pocock artifacts the review reads and their shape, the risk
zones proposed with a pointer to what suggested each one, the current
docs/agents/review.md if any, and whether writing is allowed now.

--no-gh skips the open-PR check of the write guard.
Exit status: 0 reported, 2 the repository cannot be read.
Python 3.8 or later, standard library only.
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True  # read-only: leave no __pycache__ in the plugin


def _paths():
    """This directory, review-pr's scripts (the risk map format and the run
    layout) and the plugin's copy of the finding core, the nearest
    `core/finding_core/` above it, never past the plugin's root
    (`.claude-plugin/plugin.json`): `python3 -I` puts none of them on the
    path from Python 3.11 on."""
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    while not os.path.isfile(os.path.join(d, "core", "finding_core", "__init__.py")):
        if (os.path.isfile(os.path.join(d, ".claude-plugin", "plugin.json"))
                or os.path.dirname(d) == d):
            sys.exit("finding core not found above %s" % here)
        d = os.path.dirname(d)
    review_pr = os.path.join(os.path.dirname(os.path.dirname(here)), "review-pr", "scripts")
    return [here, review_pr, os.path.join(d, "core")]


for _p in reversed(_paths()):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import repo_facts  # noqa: E402
import risk_map  # noqa: E402


def gather(repo, use_gh=True):
    files = repo_facts.list_files(repo)
    current = risk_map.load(repo)
    return {
        "repo": os.path.abspath(repo),
        "guard": repo_facts.write_guard(repo, use_gh=use_gh),
        "stacks": repo_facts.detect_stacks(files),
        "tools": repo_facts.detect_tools(repo),
        "pocock": repo_facts.check_pocock(repo),
        "proposals": repo_facts.propose_zones(repo, files),
        "current": None if current is None else {
            "stacks": current[0],
            "risk_map": [{"glob": g, "zone": z, "line": n} for g, z, n in current[1]],
            "problems": [{"line": n, "message": m} for n, m in current[2]],
        },
    }


def render(r):
    out = ["# review-setup: %s" % r["repo"], ""]
    g = r["guard"]
    out.append("## Write guard")
    out.append("")
    out.append("writing: %s (branch: %s)" % ("allowed" if g["allowed"] else "REFUSED", g["branch"] or "none"))
    out += ["- refused: %s" % x for x in g["reasons"]]
    out += ["- %s" % x for x in g["checks"]]
    out += ["", "## Stacks", ""]
    out += ["- %s: %s" % (s["name"], s["pointer"]) for s in r["stacks"]] or ["- none detected"]
    out += ["", "## Detector tools on this machine (not stored)", ""]
    for t in r["tools"]:
        out.append("- %s [%s]: %s" % (t["name"], t["stack"], t["where"] if t["found"] else "not found"))
    out += ["", "## Pocock artifacts", ""]
    for p in r["pocock"]:
        out.append("- %s `%s`: %s, %s" % (p["artifact"], p["path"], p["status"], p["detail"]))
    out += ["", "## Proposed risk zones", ""]
    if not r["proposals"]:
        out.append("- none suggested")
    for p in r["proposals"]:
        if p["glob"] is None:
            out.append("- %s: %s" % (p["zone"], p["pointer"]))
        else:
            out.append("- %s `%s` (%s: %s)" % (p["zone"], p["glob"], p["why"], p["pointer"]))
    out += ["", "## Current %s" % risk_map.PATH, ""]
    c = r["current"]
    if c is None:
        out.append("- does not exist yet")
    else:
        out.append("- stacks: %s" % (", ".join(c["stacks"]) or "none"))
        out += ["- `%s` -> %s" % (x["glob"], x["zone"]) for x in c["risk_map"]]
        out += ["- problem (line %d): %s" % (x["line"], x["message"]) for x in c["problems"]]
    return "\n".join(out) + "\n"


def main(argv):
    ap = argparse.ArgumentParser(prog="detect.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-gh", action="store_true")
    args = ap.parse_args(argv[1:])
    if not os.path.isdir(args.repo):
        print("not a directory: %s" % args.repo, file=sys.stderr)
        return 2
    report = gather(args.repo, use_gh=not args.no_gh)
    sys.stdout.write(json.dumps(report, indent=2) + "\n" if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
