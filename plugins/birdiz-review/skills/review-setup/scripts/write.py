#!/usr/bin/env python3
"""Write what the user confirmed: docs/agents/review.md and the `### Review`
subsection of the `## Agent skills` block, nothing else.

Usage: python3 -I write.py <repo> [--stack NAME]... [--zone GLOB ZONE]... [--no-gh]

review.md is replaced with exactly the given stacks and risk map rows, in
order. The `### Review` subsection is replaced in place, or added at the end
of the `## Agent skills` block; the other subsections are left untouched.

Refuses, and writes nothing, when HEAD is detached, the branch is the head
of an open PR (checked with gh when present; --no-gh skips it), review-pr
has a run directory for the branch, there is no `## Agent skills` block, or
a stack, glob or zone is malformed.
Exit status: 0 written, 1 refused, 2 the repository cannot be read.
Python 3.8 or later, standard library only.
"""
import argparse
import os
import sys

sys.dont_write_bytecode = True
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)  # python3 -I leaves it off from 3.11 on

import repo_facts  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(prog="write.py", description=__doc__.splitlines()[0])
    ap.add_argument("repo")
    ap.add_argument("--stack", action="append", default=[])
    ap.add_argument("--zone", action="append", nargs=2, metavar=("GLOB", "ZONE"), default=[])
    ap.add_argument("--no-gh", action="store_true")
    args = ap.parse_args(argv[1:])
    if not os.path.isdir(args.repo):
        print("not a directory: %s" % args.repo, file=sys.stderr)
        return 2
    written, reasons = repo_facts.write(args.repo, args.stack, [tuple(z) for z in args.zone],
                                        use_gh=not args.no_gh)
    if reasons:
        for r in reasons:
            print("REFUSED  %s" % r)
        print("nothing written")
        return 1
    for w in written:
        print("wrote    %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
