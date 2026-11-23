#!/usr/bin/env python3
"""Check that the pointers of a review run open, and that each quote is at
its line, in the findings files. Read-only.

Usage: python3 -I check-pointers.py <run directory> [--repo <path>]

A pointer is `path:line` or `path:start-end`, relative to the head tree the
run extracted (`repo-<head short sha>/`), or to --repo when given; a bare
file name is looked up under signals/; `<short sha>:path:line` reads
`repo-<short sha>/`.
Prints one line per problem, then a summary:
  MISMATCH    the quote is not at its line (says where it is, if anywhere)
  MISSING     the file does not exist, or the line is past its end
  UNRESOLVED  looks like a file name without a directory, found nowhere: read it
Whether the line proves what the text says stays with the step that owns it.
Exit status: 0 none of the first two, 1 some, 2 the run cannot be read.
Python 3.8 or later, standard library only. A thin entry point: the checks
are the finding core's, with the review extension (review_format.py).
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

from finding_core import pointers  # noqa: E402
from review_format import ReviewLayout  # noqa: E402


def main(argv):
    return pointers.main(argv, ReviewLayout, __doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
