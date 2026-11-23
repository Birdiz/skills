#!/usr/bin/env python3
"""Check an audit workspace's findings files and remediation plan against
finding-format (schema.md, SKILL.md) and remediation-plan. Read-only.

Usage: python3 -I validate.py <workspace> [--require verification] [--require plan]
       python3 -I validate.py <workspace> --fingerprint [F-...]

--fingerprint prints each finding's text hash, the `sha` a verification records
and the `sources` of a fix, and checks nothing.

Prints one line per problem, then a summary:
  ERROR    the form breaks the schema, or a rule a parser or a later step relies on
  WARNING  legacy form or a citation that does not resolve; nothing downstream breaks
  PENDING  a step still has to run (named); an error under the matching --require
Exit status: 0 no error, 1 errors, 2 the workspace cannot be read.
Python 3.8 or later, standard library only. A thin entry point: the checks
are the finding core's, with the audit extension (audit_format.py).
"""
import os
import sys

sys.dont_write_bytecode = True  # read-only: leave no __pycache__ in the plugin


def _paths():
    """This directory (the audit extension) and the plugin's copy of the
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
from audit_format import AuditExtension  # noqa: E402


def main(argv):
    return validator.main(argv, AuditExtension, __doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
