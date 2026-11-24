"""The Pocock artifact contract: the shapes the review reads, and how each
artifact is checked when it is read.

The artifacts come from `mattpocock/skills` (`setup-matt-pocock-skills`,
`to-spec`, `to-tickets`, `pr`); the review reads them and never writes
them. `pocock-contract.md`, next to this skill's SKILL.md, lists each
artifact and the sections relied on; this module is that list in code.

Every reader returns what it parsed and a `drift` list: the sections the
contract relies on that the artifact lacks. An empty list means the
artifact has the expected shape. Absent is not drift: a PR body without
`Merge Danger` is "not declared", a GitHub ticket without `Parent` or
`Blocked by` uses native relations.

Standard library only, Python 3.8 or later.
"""
import re

# The upstream commit the contract was last checked against.
UPSTREAM = "mattpocock/skills@abeeaf9"

TRACKER_DOC = "docs/agents/issue-tracker.md"
TRACKER_KINDS = ("github", "gitlab", "local markdown")

SPEC_SECTIONS = ("Problem Statement", "Solution", "User Stories", "Implementation Decisions",
                 "Testing Decisions", "Out of Scope", "Further Notes")
# The spec sections the review relies on: intent reads the decisions and
# what is out of scope; test integrity, a later slice, the testing decisions.
SPEC_RELIED_ON = ("Implementation Decisions", "Testing Decisions", "Out of Scope")

CHECKBOX = re.compile(r"^\s{0,3}[-*+]\s+\[([ xX])\]\s+(.*\S)\s*$")
ISSUE_REF = re.compile(r"(?<![\w/#])#(\d+)\b")
PART_OF = re.compile(r"(?im)^\s*\**part of\**:?\**\s+#(\d+)\b")
DOOR_LINE = re.compile(r"(?im)^\s*\*\*door:?\*\*:?\s*(.*?)\s*$")
BLAST_LINE = re.compile(r"(?im)^\s*\*\*blast radius:?\*\*:?\s*(.*?)\s*$")
LOCAL_TITLE = re.compile(r"^\d+\s*:\s*\S")
LOCAL_WHAT = re.compile(r"(?im)^\s*\*\*what to build:?\*\*")
# GitHub's closing keywords, one per reference.
CLOSING = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+"
    r"(?:(?P<owner>[\w.-]+)/(?P<name>[\w.-]+)#(?P<n1>\d+)"
    r"|#(?P<n2>\d+)"
    r"|https?://github\.com/(?P<uowner>[\w.-]+)/(?P<uname>[\w.-]+)/issues/(?P<n3>\d+))")


def headings(text):
    """[(level, title, line number)] outside fenced code blocks."""
    out, fence = [], None
    for no, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if m:
            mark = m.group(1)[0] * 3
            if fence is None:
                fence = mark
            elif mark == fence:
                fence = None
            continue
        if fence is None:
            m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
            if m:
                out.append((len(m.group(1)), m.group(2).strip(), no))
    return out


def sections(text, level=2):
    """{title: (first line number, body lines)} of the headings of `level`;
    a section ends at the next heading of that level or above."""
    lines = text.splitlines()
    hs = headings(text)
    out = {}
    for i, (lv, title, no) in enumerate(hs):
        if lv != level:
            continue
        end = next((n - 1 for l2, _, n in hs[i + 1:] if l2 <= level), len(lines))
        out.setdefault(title, (no, lines[no:end]))
    return out


def _find(secs, name):
    """The section whose title is `name`, case and trailing colon ignored."""
    want = name.lower()
    for title, value in secs.items():
        if title.rstrip(":").strip().lower() == want:
            return title, value
    return None, None


def checkboxes(lines, offset=0):
    """[{text, checked, line}] of the checkbox items in `lines`, outside
    fenced code blocks; `offset` is the line number before `lines[0]`."""
    out, fence = [], None
    for i, line in enumerate(lines):
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if m:
            mark = m.group(1)[0] * 3
            fence = mark if fence is None else (None if mark == fence else fence)
            continue
        m = CHECKBOX.match(line) if fence is None else None
        if m:
            out.append({"text": m.group(2), "checked": m.group(1) != " ", "line": offset + i + 1})
    return out


# --- The tracker doc ----------------------------------------------------------

def tracker_doc(text):
    """{status, kind, detail} of the tracker doc's text (None when missing).
    status: ok | drift | unchecked (a freeform tracker) | missing."""
    if text is None:
        return {"status": "missing", "kind": None,
                "detail": "no %s: run Pocock's `setup-matt-pocock-skills`" % TRACKER_DOC}
    hs = headings(text)
    title = next((t for lv, t, _ in hs if lv == 1), "")
    m = re.match(r"(?i)^issue tracker:\s*(.+)$", title)
    kind = m.group(1).strip() if m else None
    if not kind or kind.lower() not in TRACKER_KINDS:
        return {"status": "unchecked", "kind": kind,
                "detail": "freeform tracker (%s): its shape has no template to check" % (
                    "`# Issue tracker: %s`" % kind if kind else "no `# Issue tracker: <kind>` title")}
    if any(lv == 2 and re.search(r"(?i)fetch the relevant ticket", t) for lv, t, _ in hs):
        return {"status": "ok", "kind": kind,
                "detail": "%s tracker with a \"fetch the relevant ticket\" section" % kind}
    return {"status": "drift", "kind": kind,
            "detail": "%s tracker without a `## When a skill says \"fetch the relevant ticket\"` section" % kind}


# --- Specs and tickets --------------------------------------------------------

def shape(text):
    """`spec`, `ticket` or None, from the sections of either template."""
    secs = sections(text or "")
    spec = sum(1 for s in SPEC_SECTIONS if _find(secs, s)[0])
    ticket = bool(_find(secs, "What to build")[0] or _find(secs, "Acceptance criteria")[0]
                  or LOCAL_WHAT.search(text or ""))
    if spec >= 2 and spec >= int(ticket) * 2:
        return "spec"
    if ticket:
        return "ticket"
    return None


def read_spec(text):
    """{sections, drift}: the relied-on sections found, and the missing ones."""
    secs = sections(text or "")
    found, drift = {}, []
    for name in SPEC_RELIED_ON:
        title, value = _find(secs, name)
        if title is None:
            drift.append("no `## %s` section" % name)
        else:
            found[name] = value[0]
    return {"template": "spec", "sections": found, "drift": drift}


def read_ticket(text):
    """{template, criteria, parent, blocked_by, drift} of a ticket in either
    `to-tickets` template:

    - issue: `## What to build`, `## Acceptance criteria` with checkboxes,
      and `## Parent` / `## Blocked by` only when not native relations, so
      their absence is not drift;
    - local file: `# NN: <title>`, `**What to build:**`, bare checkboxes.
    """
    text = text or ""
    secs = sections(text)
    h1 = next((t for lv, t, _ in headings(text) if lv == 1), "")
    what_h, _ = _find(secs, "What to build")
    ac_h, ac = _find(secs, "Acceptance criteria")
    drift, criteria = [], []
    if what_h or ac_h:
        template = "issue"
        if not what_h:
            drift.append("no `## What to build` section")
        if not ac_h:
            drift.append("no `## Acceptance criteria` section")
        else:
            criteria = checkboxes(ac[1], ac[0])
            if not criteria:
                drift.append("`## Acceptance criteria` has no checkbox item")
    elif LOCAL_WHAT.search(text):
        template = "local"
        if not LOCAL_TITLE.match(h1):
            drift.append("no `# <NN>: <title>` heading")
        criteria = checkboxes(text.splitlines())
        if not criteria:
            drift.append("no acceptance criterion (a `- [ ]` item)")
    else:
        template = None
        drift.append("neither ticket template: no `What to build`")
    parent = None
    p_h, p = _find(secs, "Parent")
    if p_h:
        refs = ISSUE_REF.findall("\n".join(p[1]))
        parent = int(refs[0]) if refs else None
    m = PART_OF.search(text)
    if parent is None and m:
        parent = int(m.group(1))
    b_h, b = _find(secs, "Blocked by")
    blocked = [int(n) for n in ISSUE_REF.findall("\n".join(b[1]))] if b_h else []
    m = re.search(r"(?im)^\s*\**blocked by:?\**:?\s*(.+)$", text)
    if not b_h and m:
        blocked = [int(n) for n in ISSUE_REF.findall(m.group(1))]
    return {"template": template, "criteria": criteria, "parent": parent,
            "blocked_by": blocked, "drift": drift}


def read_artifact(text, role=None):
    """Read a spec or a ticket. `role` is what the relations say it is
    (`spec` for a ticket's parent, `ticket` for a spec's sub-issue);
    without one, its shape decides. Returns the reader's result with
    `role` set, `unknown` when neither the relations nor the shape tell."""
    role = role or shape(text)
    if role == "spec":
        out = read_spec(text)
    elif role == "ticket":
        out = read_ticket(text)
    else:
        out = {"template": None, "drift": ["neither the spec template nor a ticket template"]}
        role = "unknown"
    out["role"] = role
    return out


# --- PR bodies --------------------------------------------------------------

def read_pr_body(text):
    """{status, door, blast_radius, drift} of a PR body in the `pr` template.

    status: `declared`; `not declared` when there is no `## Merge Danger`
    (`implement-spec` opens its PR without the `pr` skill), which is not
    drift; `drift` when Merge Danger is there but a line the review compares
    is missing or unreadable."""
    text = text or ""
    title, md = _find(sections(text), "Merge Danger")
    if title is None:
        if DOOR_LINE.search(text):
            return {"status": "drift", "door": None, "blast_radius": None,
                    "drift": ["a `**Door:**` line outside a `## Merge Danger` section"]}
        return {"status": "not declared", "door": None, "blast_radius": None, "drift": []}
    body = "\n".join(md[1])
    drift, door, blast = [], None, None
    m = DOOR_LINE.search(body)
    if not m:
        drift.append("`## Merge Danger` has no `**Door:**` line")
    else:
        value = re.sub(r"[\s_]+", "-", m.group(1).strip().strip("`*_.").lower())
        if value in ("one-way", "two-way"):
            door = value
        else:
            drift.append("Door `%s` is neither one-way nor two-way" % m.group(1).strip())
    m = BLAST_LINE.search(body)
    if not m or not m.group(1).strip():
        drift.append("`## Merge Danger` has no `**Blast Radius:**` line")
    else:
        blast = m.group(1).strip().strip("`*_.")
    return {"status": "drift" if drift else "declared", "door": door, "blast_radius": blast, "drift": drift}


# --- The domain doc, the glossary and the ADRs ------------------------------------

DOMAIN_DOC = "docs/agents/domain.md"
GLOSSARY = "GLOSSARY.md"
GLOSSARY_MAP = "GLOSSARY-MAP.md"
DEFAULT_ADR_DIR = "docs/adr"
ADR_DIR = re.compile(r"`?((?:[\w.<>-]+/)*adr)/`?")
LEGACY_GLOSSARY = re.compile(r"\bCONTEXT(?:-MAP)?\.md\b")
# `**Order**:` in Pocock's GLOSSARY-FORMAT, `- **Order**: ...` as a list.
TERM_LINE = re.compile(r"^\s{0,3}(?:[-*+]\s+)?\*\*(?P<term>[^*]+?)\s*:?\s*\*\*\s*:")
AVOID_LINE = re.compile(r"^\s{0,6}(?:[-*+]\s+)?[_*]{1,2}Avoid[_*]{1,2}\s*:?[_*]{0,2}\s*:?\s*(?P<words>.+?)\s*$", re.I)
MAP_LINK = re.compile(r"\[[^\]]*\]\(\s*(?:\./)?(?P<path>[^)\s#]+\.md)\s*\)")


def domain_doc(text, map_exists=False):
    """{legacy, names_glossary, names_map, adr_dirs, glossary_drift,
    adr_drift} of the domain doc's text. `map_exists` says whether
    `GLOSSARY-MAP.md` exists: Pocock's doc names both files ("or
    GLOSSARY-MAP.md if it exists"), so naming the map counts only then, or
    when the doc names no GLOSSARY.md."""
    text = text or ""
    legacy = sorted(set(LEGACY_GLOSSARY.findall(text)))
    names_glossary = GLOSSARY in text.replace(GLOSSARY_MAP, "")
    names_map = GLOSSARY_MAP in text and (not names_glossary or map_exists)
    adr_dirs = sorted(set(ADR_DIR.findall(text)))
    glossary_drift, adr_drift = [], []
    if legacy:
        glossary_drift.append("names legacy %s; the review reads GLOSSARY.md / GLOSSARY-MAP.md" % ", ".join(legacy))
    if not (names_glossary or names_map):
        glossary_drift.append("names no GLOSSARY.md or GLOSSARY-MAP.md")
    if not adr_dirs:
        adr_drift.append("names no ADR directory (e.g. docs/adr/)")
    return {"legacy": legacy, "names_glossary": names_glossary, "names_map": names_map, "adr_dirs": adr_dirs,
            "glossary_drift": glossary_drift, "adr_drift": adr_drift}


def glossary_terms(text):
    """[{term, line, avoid}] of a glossary in Pocock's format: a term is a
    bold `**Term**:` at the start of a line (or of a list item), and an
    `_Avoid_:` line under it lists the words not to use for it."""
    out, fence = [], None
    for no, line in enumerate((text or "").splitlines(), 1):
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if m:
            mark = m.group(1)[0] * 3
            fence = mark if fence is None else (None if mark == fence else fence)
            continue
        if fence is not None:
            continue
        m = TERM_LINE.match(line)
        if m:
            out.append({"term": m.group("term").strip(), "line": no, "avoid": []})
            continue
        m = AVOID_LINE.match(line)
        if m and out:
            words = re.sub(r"[_*]", "", m.group("words"))
            out[-1]["avoid"] += [w.strip(" .") for w in words.split(",") if w.strip(" .")]
    return out


def glossary_map(text):
    """The glossary files a `GLOSSARY-MAP.md` links to, relative to the root."""
    out = []
    for m in MAP_LINK.finditer(text or ""):
        path = m.group("path").lstrip("/")
        if path not in out and not path.startswith(("http:", "https:")):
            out.append(path)
    return out


# --- References -----------------------------------------------------------------

def closing_refs(body, repo=None):
    """Issue numbers a PR body closes with GitHub's keywords, one keyword per
    reference (`Closes #1, #2` closes #1 only), in order. A reference to
    another repository than `repo` (`owner/name`) is left out."""
    out = []
    for m in CLOSING.finditer(body or ""):
        owner = m.group("owner") or m.group("uowner")
        name = m.group("name") or m.group("uname")
        if owner and repo and "%s/%s" % (owner, name) != repo:
            continue
        n = int(m.group("n1") or m.group("n2") or m.group("n3"))
        if n not in out:
            out.append(n)
    return out


def issue_refs(text):
    """`#N` references in a text, in order, without repeats."""
    out = []
    for n in ISSUE_REF.findall(text or ""):
        if int(n) not in out:
            out.append(int(n))
    return out
