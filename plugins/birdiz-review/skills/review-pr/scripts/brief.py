#!/usr/bin/env python3
"""Regenerate a review run's brief from its run header, detector outputs
and findings files. The brief is a projection: never edit it, run this
after any step writes its findings.

Usage: python3 -I brief.py <run directory>

Writes <run directory>/brief.md and prints its verdict line.
Exit status: 0 written, 2 the run directory cannot be read.
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

import review_format as fmt  # noqa: E402


def main(argv):
    args = argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        run = fmt.Run(args[0])
    except fmt.RunError as e:
        print("not a run directory: %s" % e, file=sys.stderr)
        return 2
    text = fmt.render_brief(run)
    with open(os.path.join(args[0], fmt.BRIEF), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(next((line for line in text.split("\n") if line.startswith("Proposed verdict:")), ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
