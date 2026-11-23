"""The finding core: the rules every plugin's findings share, and the checks
that read them. Python 3.8 or later, standard library only.

- `markdown`: the flat YAML subset and the Markdown structure findings use.
- `report`: the ERROR / WARNING / PENDING lines a check prints.
- `validator`: the finding schema core (evidence, finding and lead, status
  owned by a verifier, severity and confidence, coverage, `sensitive`,
  `promptable`, ID shapes), parameterized by a plugin's `Extension`.
- `pointers`: the pointer and quote check, with the workspace layout a
  plugin's `Layout` supplies.

A plugin keeps a copy of this directory at its root; its scripts put that
copy on the import path themselves, since `python3 -I` adds no script
directory from Python 3.11 on.
"""

VERSION = "0.1.0"
NAME = "finding-core@" + VERSION
