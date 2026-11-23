"""The intent findings file: the worksheet `run.py` writes, the tables the
intent step fills in, and what the validator and the verdict read from them.

`findings/intent.md` holds, between its coverage and its findings, three
tables:

- `## Criteria`: one row per acceptance criterion of the in-scope tickets,
  `<ticket ref> AC<n>`, with its status (`found`, `partial`, `not found`),
  the hunks that implement it and the finding that says what is missing;
- `## Files`: one row per changed file, with the tickets or criteria that
  justify it, or `out of scope` and its finding;
- `## Decisions`: one row per change that contradicts an item of the spec's
  Implementation Decisions or Out of Scope, with its finding; `None.` when
  nothing does.

`run.py` writes the rows of the first two from `sources.json` and the git
changes, with `?` where the step judges, so no criterion and no file can be
left out. The step replaces each `?`. The validator checks the result
against `sources.json`, the changed files and their hunks; the verdict
counts it.
"""
import os
import re

from finding_core import pointers
from finding_core.markdown import blocks, read
import pocock

AXIS = "intent"
NOT_RUN_YET = "step not run yet"
STEP_FILE = "steps/intent.md"
SECTIONS = ["Criteria", "Files", "Decisions"]
STATUSES = ["found", "partial", "not found"]
OUT_OF_SCOPE = "out of scope"
UNFILLED = "?"
DECISION_SECTIONS = ("Implementation Decisions", "Out of Scope")
AREAS = ["Criteria to hunks", "Files to tickets or criteria", "Out of scope and decisions"]
CID = re.compile(r"^(?P<ref>\S+) AC(?P<n>\d+)\b")
FID = re.compile(r"\bF-[A-Z0-9]+-\d+\b")
ENTRY = re.compile(r"^(?P<path>.+?)(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?$")
QUOTE_MAX = 100


# --- What the sources say -----------------------------------------------------

def artifacts(found):
    return [a for a in ((found or {}).get("artifacts") or []) if isinstance(a, dict)]


def dimension(found):
    """The intent dimension `sources.json` records, `evaluable` or
    `not-evaluable (<why>)`."""
    if not isinstance(found, dict):
        return "not-evaluable (sources not read)"
    return str((found.get("dimensions") or {}).get("intent") or "not-evaluable (sources not read)")


def criteria(found):
    """[{cid, ref, text, line, file}] of the in-scope tickets read, in order."""
    out = []
    for a in artifacts(found):
        if a.get("role") == "ticket" and a.get("scope") == "in scope" and a.get("status") == "ok":
            for n, c in enumerate(a.get("criteria") or [], 1):
                out.append({"cid": "%s AC%d" % (a["ref"], n), "ref": a["ref"], "text": str(c.get("text") or ""),
                            "line": c.get("line"), "file": a.get("file")})
    return out


def scope(found):
    """(refs that justify a change, sibling ticket refs): the in-scope
    tickets and the spec, and the spec's other tickets."""
    ok, siblings = set(), set()
    for a in artifacts(found):
        if a.get("status") == "unreadable":
            continue
        if a.get("scope") == "sibling":
            siblings.add(a["ref"])
        elif a.get("role") in ("ticket", "spec"):
            ok.add(a["ref"])
    return ok, siblings


def spec_artifact(found):
    return next((a for a in artifacts(found) if a.get("role") == "spec" and a.get("status") != "unreadable"), None)


# --- The worksheet ------------------------------------------------------------

def cell(text):
    return str(text).replace("|", "\\|")


def quote(text):
    """The criterion's words for a quote the pointer check can verify: up to
    the first double quote, cut at QUOTE_MAX characters with an elision."""
    text = " ".join(text.split())
    head = text.split('"', 1)[0].rstrip()
    cut = head != text
    if len(head) > QUOTE_MAX:
        head, cut = head[:QUOTE_MAX - 1].rstrip(), True
    if len(head) < 3:
        return ""
    return ' "%s%s"' % (cell(head), "…" if cut else "")


def worksheet(found, changed, version):
    """The intent findings file before the step runs: every row the step
    must fill, `?` where it judges."""
    rows = ["| %s | not-evaluable | Step not run yet: run %s. |" % (area, STEP_FILE) for area in AREAS]
    out = ["# Intent", "", "## Coverage", "", "skill: %s, tools: []" % version, "",
           "| Area | Status | Notes |", "|---|---|---|"] + rows + [
           "", "Axis: not-evaluable (%s)" % NOT_RUN_YET, "", "## Criteria", ""]
    crit = criteria(found)
    if crit:
        out += ["| Criterion | Status | Hunks | Finding |", "|---|---|---|---|"]
        for c in crit:
            where = " `%s:%s`%s" % (c["file"], c["line"], quote(c["text"])) if c["file"] and c["line"] else ""
            out.append("| %s%s | %s | | |" % (c["cid"], where, UNFILLED))
    else:
        out.append("None.")
    out += ["", "## Files", "", "| File | Justified by | Finding |", "|---|---|---|"]
    out += ["| `%s` | %s | |" % (cell(p), UNFILLED) for p in changed]
    out += ["", "## Decisions", "", "None.", "", "## Findings", "", "None.", "", "## Leads", "", "None.", ""]
    return "\n".join(out)


# --- Reading the tables ---------------------------------------------------------

def split_row(line):
    t = line.strip()
    t = t[1:] if t.startswith("|") else t
    t = t[:-1] if t.endswith("|") and not t.endswith("\\|") else t
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", t)]


def table(items):
    """[(line number, cells)] of the body rows of the first table in a section."""
    rows, header = [], None
    for i, line, _, _ in items:
        if line is None or not line.strip().startswith("|"):
            if header is not None:
                break
            continue
        cells = split_row(line)
        if header is None:
            header = cells
        elif not set("".join(cells)) <= set("-: "):
            rows.append((i + 1, cells))
    return rows


def entries(text):
    """The hunk entries of a cell: `path:start-end`, `path:line` or `path`."""
    out = []
    for raw in re.findall(r"`([^`]+)`", text):
        m = ENTRY.match(raw.strip())
        start = int(m.group("start")) if m.group("start") else None
        out.append({"raw": raw, "path": m.group("path"), "start": start,
                    "end": int(m.group("end")) if m.group("end") else start})
    return out


def read_file(path):
    """{sections, criteria, files, decisions} of an intent findings file."""
    lines = read(path)
    secs = {name: items for name, _, items in blocks(lines, 2)[1:]}
    out = {"sections": [n for n in secs if n in SECTIONS], "criteria": [], "files": [], "decisions": []}
    for line, cells in table(secs.get("Criteria", [])):
        cells += [""] * (4 - len(cells))
        m = CID.match(cells[0])
        out["criteria"].append({"line": line, "cid": "%s AC%s" % (m.group("ref"), m.group("n")) if m else cells[0],
                                "status": cells[1].strip().lower(), "hunks": entries(cells[2]),
                                "findings": FID.findall(cells[3])})
    for line, cells in table(secs.get("Files", [])):
        cells += [""] * (3 - len(cells))
        m = re.search(r"`([^`]+)`", cells[0])
        just = [j.strip().strip("`").strip() for j in cells[1].split(",")]
        out["files"].append({"line": line, "path": m.group(1) if m else cells[0].strip(),
                             "justified": [j for j in just if j], "findings": FID.findall(cells[2])})
    for line, cells in table(secs.get("Decisions", [])):
        cells += [""] * (3 - len(cells))
        m = pointers.POINTER.search(cells[0])
        out["decisions"].append({"line": line, "item": cells[0],
                                 "pointer": (m.group("path"), int(m.group("start"))) if m else None,
                                 "changes": entries(cells[1]), "findings": FID.findall(cells[2])})
    return out


def out_of_scope(row):
    return [j.lower() for j in row["justified"]] == [OUT_OF_SCOPE]


def summary(it):
    """The counts the verdict and the brief give."""
    crit = it["criteria"]
    count = {s: sum(1 for c in crit if c["status"] == s) for s in STATUSES}
    files = it["files"]
    oos = [f for f in files if out_of_scope(f)]
    return {"criteria": len(crit), "found": count["found"], "partial": count["partial"],
            "not found": count["not found"], "files": len(files), "out of scope": oos,
            "decisions": it["decisions"]}


def close_reasons(it):
    """Why misread intent proposes `close-and-reprompt`, empty when it does not."""
    s = summary(it)
    out = []
    if s["criteria"] and s["not found"] * 2 > s["criteria"]:
        out.append("Intent misread: %d of %d acceptance criteria not found (%s)." % (
            s["not found"], s["criteria"],
            ", ".join(c["cid"] for c in it["criteria"] if c["status"] == "not found")))
    if s["decisions"]:
        out.append("Work against the spec's stated decisions: %s." % ", ".join(
            "%s (%s)" % ("/".join(d["findings"]) or "no finding", ", ".join(e["raw"] for e in d["changes"]))
            for d in s["decisions"]))
    if s["out of scope"]:
        out.append("Out-of-scope edits beyond the touched tickets: %s." % ", ".join(
            "`%s` (%s)" % (f["path"], "/".join(f["findings"]) or "no finding") for f in s["out of scope"]))
    return out


def summary_line(it):
    s = summary(it)
    return ("Intent: %d of %d acceptance criteria found, %d partial, %d not found; %d of %d changed files"
            " justified, %d out of scope; %d change(s) against a stated decision." % (
                s["found"], s["criteria"], s["partial"], s["not found"], s["files"] - len(s["out of scope"]),
                s["files"], len(s["out of scope"]), len(s["decisions"])))


# --- The validator's checks -------------------------------------------------------

def decision_ranges(root, spec):
    """[(first line, last line)] of the spec copy's Implementation Decisions
    and Out of Scope sections."""
    try:
        with open(os.path.join(root, str(spec.get("file"))), encoding="utf-8", newline="") as fh:
            text = fh.read()
    except OSError:
        return []
    secs = pocock.sections(text)
    out = []
    for name in DECISION_SECTIONS:
        _, value = pocock._find(secs, name)
        if value:
            out.append((value[0], value[0] + len(value[1])))
    return out


class Check:
    """The intent file checked against the run: `error(line, message)` and
    `pending(line, message)` report on the intent findings file."""

    def __init__(self, root, found, changes, findings, error, pending):
        self.root, self.found, self.changes = root, found, changes
        self.findings = findings
        self.error, self.pending = error, pending

    def run(self, path, axis_status):
        status, why = axis_status
        dim = dimension(self.found)
        if status == "not-evaluable" and why == NOT_RUN_YET:
            self.pending(None, "the intent step has not run on this run directory: run %s" % STEP_FILE)
            return None
        if dim != "evaluable":
            if status in ("evaluated", "partial"):
                self.error(None, "intent is %s, but its sources are %s: the step runs only on evaluable sources"
                           % (status, dim))
            return None
        if status not in ("evaluated", "partial"):
            return None
        it = read_file(path)
        for name in SECTIONS:
            if name not in it["sections"]:
                self.error(None, "section `## %s` missing: an evaluated intent step fills it" % name)
        cited = set()
        self.check_criteria(it, cited)
        self.check_files(it, cited)
        self.check_decisions(it, cited)
        for fid in sorted(self.findings):
            if fid not in cited:
                self.error(self.findings[fid], "%s is cited by no row of Criteria, Files or Decisions" % fid)
        return it

    def cite(self, line, row, cited, required, what):
        fids = row["findings"]
        if required and not fids:
            self.error(line, "%s needs the finding that says why" % what)
        for fid in fids:
            if fid not in self.findings:
                self.error(line, "%s cites %s, which is not a finding of this file" % (what, fid))
            cited.add(fid)

    def check_criteria(self, it, cited):
        expected = criteria(self.found)
        want = [c["cid"] for c in expected]
        seen = {}
        for row in it["criteria"]:
            line, cid = row["line"], row["cid"]
            if cid in seen:
                self.error(line, "%s has two rows (also line %d)" % (cid, seen[cid]))
            seen.setdefault(cid, line)
            if cid not in want:
                self.error(line, "%s is not an acceptance criterion of an in-scope ticket in sources.json" % cid)
            if row["status"] == UNFILLED:
                self.error(line, "%s: status left `?`" % cid)
                continue
            if row["status"] not in STATUSES:
                self.error(line, "%s: status `%s` not in %s" % (cid, row["status"], " | ".join(STATUSES)))
                continue
            if row["status"] in ("found", "partial") and not row["hunks"]:
                self.error(line, "%s is %s but names no hunk" % (cid, row["status"]))
            if row["status"] == "not found" and row["hunks"]:
                self.error(line, "%s is not found but names hunks" % cid)
            for e in row["hunks"]:
                self.check_entry(line, e)
            self.cite(line, row, cited, row["status"] != "found", "%s (%s)" % (cid, row["status"]))
        for cid in want:
            if cid not in seen:
                self.error(None, "%s has no row in `## Criteria`" % cid)

    def check_files(self, it, cited):
        ok, siblings = scope(self.found)
        cids = {c["cid"]: c["ref"] for c in criteria(self.found)}
        seen = {}
        for row in it["files"]:
            line, p = row["line"], row["path"]
            if p in seen:
                self.error(line, "`%s` has two rows (also line %d)" % (p, seen[p]))
            seen.setdefault(p, line)
            if p not in self.changes:
                self.error(line, "`%s` is not a changed file" % p)
            just = row["justified"]
            if not just or just == [UNFILLED]:
                self.error(line, "`%s`: justification left `?`" % p)
                continue
            if out_of_scope(row):
                self.cite(line, row, cited, True, "`%s` (out of scope)" % p)
                continue
            for j in just:
                m = CID.match(j)
                ref = m.group("ref") if m else j
                if j.lower() == OUT_OF_SCOPE:
                    self.error(line, "`%s`: `out of scope` stands alone" % p)
                elif ref in siblings:
                    self.error(line, "`%s` is justified by %s, a sibling ticket: that is out of scope, flag it" % (p, j))
                elif (m and j not in cids) or (not m and ref not in ok):
                    self.error(line, "`%s` is justified by %s, which is not an in-scope ticket, criterion or the spec"
                               % (p, j))
            self.cite(line, row, cited, False, "`%s`" % p)
        for p in self.changes:
            if p not in seen:
                self.error(None, "changed file `%s` has no row in `## Files`" % p)

    def check_decisions(self, it, cited):
        spec = spec_artifact(self.found)
        ranges = decision_ranges(self.root, spec) if spec else []
        for row in it["decisions"]:
            line = row["line"]
            if spec is None:
                self.error(line, "a decision row, but no spec was read")
            elif row["pointer"] is None or row["pointer"][0] != spec.get("file"):
                self.error(line, "the spec item is not a pointer into the spec's copy, `%s:<line>`" % spec.get("file"))
            elif not any(lo <= row["pointer"][1] <= hi for lo, hi in ranges):
                self.error(line, "`%s:%d` is in neither Implementation Decisions nor Out of Scope"
                           % row["pointer"])
            if not row["changes"]:
                self.error(line, "a decision row names no change")
            for e in row["changes"]:
                self.check_entry(line, e)
            self.cite(line, row, cited, True, "the decision row")

    def check_entry(self, line, e):
        """A hunk entry: a changed file, and lines that meet one of its hunks;
        the path alone only for a file with no line hunk (deleted, renamed
        unchanged, binary)."""
        change = self.changes.get(e["path"])
        if change is None:
            self.error(line, "`%s`: `%s` is not a changed file" % (e["raw"], e["path"]))
            return
        ranges = change.get("hunks") or []
        if e["start"] is None:
            if ranges and change.get("change") != "deleted":
                self.error(line, "`%s`: give the hunk's lines, `%s:<start>-<end>`" % (e["raw"], e["path"]))
            return
        if change.get("change") == "deleted":
            self.error(line, "`%s`: a deleted file has no lines in the head, give the path alone" % e["raw"])
            return
        start, end = e["start"], e["end"]
        if end < start:
            self.error(line, "`%s`: the range ends before it starts" % e["raw"])
            return
        for s, c in ranges:
            lo, hi = (s, s + c - 1) if c else (s, s + 1)
            if start <= hi and end >= lo:
                return
        self.error(line, "`%s`: no hunk of `%s` meets these lines (hunks %s)" % (
            e["raw"], e["path"], ", ".join("%d-%d" % (s, s + max(c, 1) - 1) for s, c in ranges) or "none"))
