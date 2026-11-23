"""The repo facts of `docs/agents/review.md`: stacks and the risk map.

`review-setup` renders the file, `review-pr` parses it and asks which risk
zones a changed file is in. Standard library only, Python 3.8 or later.

The file:

    # Review

    <one paragraph>

    ## Stacks

    - php

    ## Risk map

    <one paragraph>

    | Glob | Zone |
    |---|---|
    | `src/Security/**` | auth |

Globs are gitignore-like and relative to the repository root:
- `*` matches within one path segment, `?` one character, `[abc]` a class;
- `**` spans segments: `**/x`, `a/**`, `a/**/b`;
- a glob with no `/` (apart from a trailing one) matches a name at any
  depth: `*.sql`, `migrations`;
- a leading `/` anchors to the root, which every glob with a `/` already is;
- a trailing `/` matches directories only;
- a glob that matches a directory matches every file under it.
Negation (`!`) is not supported.
"""
import re

PATH = "docs/agents/review.md"
ZONES = ("auth", "personal-data", "payments", "concurrency", "irreversible", "public-api")
ZONE_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
STACK_NAME = ZONE_NAME

INTRO = ("Repo facts for the `birdiz-review` skills, written by `review-setup`. "
         "Edit them by hand or run `review-setup` again.")
RISK_INTRO = ("A changed file that matches a glob is never `skim` in a review brief. "
              "Globs are gitignore-like and relative to the repository root.")


class GlobError(ValueError):
    pass


def glob_problem(glob):
    """Why `glob` can't be used, or None."""
    if not glob or not glob.strip():
        return "empty glob"
    if glob != glob.strip():
        return "leading or trailing spaces"
    if glob.startswith("!"):
        return "negation (!) is not supported"
    if "|" in glob or "`" in glob:
        return "| and ` can't appear in a glob"
    if "\\" in glob:
        return "backslashes are not supported; use / between directories"
    body = glob.strip("/")
    if not body:
        return "the glob matches nothing"
    if any(part in (".", "..") for part in body.split("/")):
        return ". and .. segments are not supported"
    try:
        re.compile(_translate(body))
    except (ValueError, re.error):
        return "unbalanced [ ]"
    return None


def _translate(body):
    out = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "*":
            if body.startswith("**", i):
                start = i == 0 or body[i - 1] == "/"
                end = i + 2 == n or body[i + 2] == "/"
                if start and end:
                    if i + 2 == n:          # a/** or a lone **
                        out.append(".*")
                        i += 2
                    else:                   # **/ at the start or in the middle
                        out.append("(?:.*/)?")
                        i += 3
                    continue
                out.append("[^/]*")         # ** inside a segment acts as *
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[":
            j = body.index("]", i + 1)
            inner = body[i + 1:j]
            neg = inner[:1] in ("!", "^")
            if neg:
                inner = inner[1:]
            out.append("[" + ("^/" if neg else "") + inner.replace("\\", "\\\\") + "]")
            i = j
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


def compile_glob(glob):
    """A predicate path -> bool for one glob (raises GlobError)."""
    problem = glob_problem(glob)
    if problem:
        raise GlobError("%s: %s" % (glob, problem))
    dir_only = glob.endswith("/")
    body = glob.strip("/")
    anywhere = not glob.startswith("/") and "/" not in body
    pattern = ("(?:.*/)?" if anywhere else "") + _translate(body)
    rx = re.compile(pattern + r"\Z", re.DOTALL)

    def match(path):
        parts = path.strip("/").split("/")
        last = len(parts) if not dir_only else len(parts) - 1
        for k in range(1, last + 1):
            if rx.match("/".join(parts[:k])):
                return True
        return False

    return match


def render(stacks, rows):
    """review.md for these stacks and (glob, zone) rows, in the given order."""
    lines = ["# Review", "", INTRO, "", "## Stacks", ""]
    lines += ["- %s" % s for s in stacks] or ["_none detected_"]
    lines += ["", "## Risk map", "", RISK_INTRO, "", "| Glob | Zone |", "|---|---|"]
    lines += ["| `%s` | %s |" % (g, z) for g, z in rows]
    return "\n".join(lines) + "\n"


def _cells(line):
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return None
    return [c.strip() for c in s[1:-1].split("|")]


def parse(text):
    """(stacks, rows, problems) from the text of review.md.

    rows are (glob, zone, line number). A problem is (line number, message);
    a row with a problem is left out of rows, so a reader can carry on."""
    stacks, rows, problems = [], [], []
    section = None
    seen_header = False
    found = set()
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            title = m.group(2).strip().lower()
            section = title if len(m.group(1)) == 2 else (None if len(m.group(1)) == 1 else section)
            if len(m.group(1)) == 2:
                found.add(title)
            continue
        if section == "stacks":
            m = re.match(r"^\s*[-*]\s+`?([^`\s]+)`?\s*$", line)
            if m:
                name = m.group(1).lower()
                if STACK_NAME.match(name):
                    stacks.append(name)
                else:
                    problems.append((no, "stack %r is not a lowercase name" % m.group(1)))
        elif section == "risk map":
            cells = _cells(line)
            if cells is None:
                continue
            if not seen_header:
                if [c.lower() for c in cells[:2]] != ["glob", "zone"]:
                    problems.append((no, "the risk map table must start with | Glob | Zone |"))
                seen_header = True
                continue
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if len(cells) != 2:
                problems.append((no, "a risk map row has two cells, glob and zone"))
                continue
            glob = cells[0]
            if len(glob) >= 2 and glob.startswith("`") and glob.endswith("`"):
                glob = glob[1:-1]
            zone = cells[1].strip("`").strip()
            why = glob_problem(glob)
            if why:
                problems.append((no, "glob %r: %s" % (glob, why)))
            elif not ZONE_NAME.match(zone):
                problems.append((no, "zone %r is not a lowercase-hyphen name" % zone))
            else:
                rows.append((glob, zone, no))
    for name, heading in (("stacks", "Stacks"), ("risk map", "Risk map")):
        if name not in found:
            problems.append((0, "no `## %s` section" % heading))
    return stacks, rows, problems


def zones_for(path, rows):
    """[(zone, glob)] for every row whose glob matches `path`, in file order,
    one entry per zone."""
    out, seen = [], set()
    for row in rows:
        glob, zone = row[0], row[1]
        if zone in seen:
            continue
        if compile_glob(glob)(path):
            out.append((zone, glob))
            seen.add(zone)
    return out


def load(repo):
    """parse() of the repo's review.md, or None when it does not exist."""
    import os
    p = os.path.join(repo, *PATH.split("/"))
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return parse(fh.read())
