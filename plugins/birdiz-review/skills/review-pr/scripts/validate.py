#!/usr/bin/env python3
"""Check a review run directory against the review schema: the findings
files (the finding core with the review extension), the run header, the
detector outputs and the brief. Read-only.

Usage: python3 -I validate.py <run directory> [--require brief]
       python3 -I validate.py <run directory> --fingerprint [F-...]

Besides the findings, it checks that every changed file is in exactly one
bucket of the brief, that each skim file rests on content detector outputs
that covered it with no signal and no finding, and the verdict line with its
round count.
Prints one line per problem, then a summary:
  ERROR    the form breaks the schema, or a rule the brief or a later step relies on
  WARNING  a citation that does not resolve; nothing downstream breaks
  PENDING  a step still has to run (named): `brief` when brief.md is not the
           projection of the files as they are now, an error under --require brief
Exit status: 0 no error, 1 errors, 2 the run directory cannot be read.
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

from finding_core import validator  # noqa: E402
from review_format import ReviewExtension  # noqa: E402


def main(argv):
    return validator.main(argv, ReviewExtension, __doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
