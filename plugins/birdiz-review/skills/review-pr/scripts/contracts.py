"""The contracts findings file: the worksheet `run.py` writes, the tables the
contracts step fills in, and what the validator, the brief and the verdict
read from them.

`findings/contracts.md` holds, between its coverage and its findings, two
tables:

- `## Signals`: one row per signal of the detectors (all but
  `git-changes`), `S<n>` in the order of the run header's detectors, with
  its judgment: `one-way` (reverting the merge does not undo it: data
  dropped or rewritten, a contract consumers already rely on), `breaking`
  (a consumer outside the diff breaks, and a revert undoes it) or `minor`,
  and the finding that says why for the first two;
- `## Declared`: one row, the PR's declared Door and Blast Radius, the Door
  the step detected (`one-way` or `two-way`), and the disagreement finding
  when the two Doors differ.

`run.py` writes every row with `?` where the step judges, so no signal can
be left out. The validator checks the rows against the detector outputs
and `sources.json`; the brief shows the detected Door beside the declared
one; the verdict counts the judgments.
"""
import re

from finding_core.markdown import blocks, read
import intent

AXIS = "contracts"
NOT_RUN_YET = intent.NOT_RUN_YET
STEP_FILE = "steps/contracts.md"
SECTIONS = ["Signals", "Declared"]
JUDGMENTS = ["one-way", "breaking", "minor"]
DOORS = ["one-way", "two-way"]
AREAS = ["Code API", "Routes and wire contracts", "Persistence", "Configuration",
         "Behaviour (assertions)", "Fan-in", "Declared vs detected"]
NOT_SIGNALS = ("git-changes",)
SID = re.compile(r"^S(\d+)\b")
FID = intent.FID
UNFILLED = intent.UNFILLED


# --- What the run says ------------------------------------------------------------

def signal_rows(outputs):
    """[{sid, rel, detector, path, line, kind, reason}]: every signal of the
    detectors but git-changes, in the order of `outputs` [(rel, output)]."""
    out = []
    for rel, o in outputs:
        if not isinstance(o, dict) or o.get("detector") in NOT_SIGNALS:
            continue
        for s in o.get("signals") or []:
            if isinstance(s, dict) and s.get("path"):
                out.append({"sid": "S%d" % (len(out) + 1), "rel": rel, "detector": o.get("detector") or rel,
                            "path": s["path"], "line": s.get("line"), "kind": s.get("kind") or "signal",
                            "reason": s.get("reason") or ""})
    return out


def pr_body(found):
    pr = (found or {}).get("pr") if isinstance(found, dict) else None
    return pr if isinstance(pr, dict) else None


def declared_door(found):
    """The Door the PR body declares, or None when it declares none."""
    pr = pr_body(found)
    return pr.get("door") if pr and pr.get("status") == "declared" else None


def declared_cell(found):
    pr = pr_body(found)
    if pr is None:
        return "not declared: no PR body read"
    number = pr.get("number")
    if pr.get("status") == "declared":
        return "PR #%s: Door `%s`, Blast Radius `%s`" % (number, pr.get("door"), pr.get("blast_radius"))
    if pr.get("status") == "not declared":
        return "not declared: PR #%s has no `Merge Danger`" % number
    return "not read: PR #%s body, contract drift" % number


# --- The worksheet --------------------------------------------------------------------

def signal_cell(row):
    where = "`%s:%d`" % (row["path"], row["line"]) if row.get("line") else "`%s`" % row["path"]
    return "%s %s %s `%s`: %s" % (row["sid"], where, row["detector"], row["kind"], intent.cell(row["reason"]))


def worksheet(outputs, found, version):
    """The contracts findings file before the step runs: one row per signal
    and the declared row, `?` where it judges."""
    rows = ["| %s | not-evaluable | Step not run yet: run %s. |" % (area, STEP_FILE) for area in AREAS]
    out = ["# Contracts", "", "## Coverage", "", "skill: %s, tools: []" % version, "",
           "| Area | Status | Notes |", "|---|---|---|"] + rows + [
           "", "Axis: not-evaluable (%s)" % NOT_RUN_YET, "", "## Signals", ""]
    sig = signal_rows(outputs)
    if sig:
        out += ["| Signal | Judgment | Finding |", "|---|---|---|"]
        out += ["| %s | %s | |" % (signal_cell(r), UNFILLED) for r in sig]
    else:
        out.append("None.")
    out += ["", "## Declared", "", "| Declared | Detected | Finding |", "|---|---|---|",
            "| %s | %s | |" % (declared_cell(found), UNFILLED),
            "", "## Findings", "", "None.", "", "## Leads", "", "None.", ""]
    return "\n".join(out)


# --- Reading the tables ------------------------------------------------------------------

def read_file(path):
    """{sections, signals, declared} of a contracts findings file."""
    lines = read(path)
    secs = {name: items for name, _, items in blocks(lines, 2)[1:]}
    out = {"sections": [n for n in secs if n in SECTIONS], "signals": [], "declared": []}
    for line, cells in intent.table(secs.get("Signals", [])):
        cells += [""] * (3 - len(cells))
        m = SID.match(cells[0])
        out["signals"].append({"line": line, "sid": "S%s" % m.group(1) if m else cells[0], "cell": cells[0],
                               "judgment": cells[1].strip().lower(), "findings": FID.findall(cells[2])})
    for line, cells in intent.table(secs.get("Declared", [])):
        cells += [""] * (3 - len(cells))
        out["declared"].append({"line": line, "declared": cells[0], "detected": cells[1].strip().strip("`").lower(),
                                "findings": FID.findall(cells[2])})
    return out


def detected_door(it):
    """The Door the step detected, or None."""
    rows = (it or {}).get("declared") or []
    door = rows[0]["detected"] if rows else None
    return door if door in DOORS else None


def one_way_rows(it):
    return [r for r in (it or {}).get("signals") or [] if r["judgment"] == "one-way"]


def summary(it):
    sig = it["signals"]
    return {j: sum(1 for r in sig if r["judgment"] == j) for j in JUDGMENTS}, len(sig)


def summary_line(it):
    counts, total = summary(it)
    return "Contracts: %d signal(s) judged, %d one-way, %d breaking, %d minor; detected Door %s." % (
        total, counts["one-way"], counts["breaking"], counts["minor"], detected_door(it) or "not given")


# --- The validator's checks -----------------------------------------------------------------

class Check:
    """The contracts file checked against the run: `error(line, message)` and
    `pending(line, message)` report on the contracts findings file.
    `findings` maps each finding ID of this file to its ReviewFinding."""

    def __init__(self, outputs, found, findings, error, pending):
        self.outputs, self.found, self.findings = outputs, found, findings
        self.error, self.pending = error, pending

    def run(self, path, axis_status):
        status, why = axis_status
        if status == "not-evaluable" and why == NOT_RUN_YET:
            self.pending(None, "the contracts step has not run on this run directory: run %s" % STEP_FILE)
            return None
        if status not in ("evaluated", "partial"):
            return None
        it = read_file(path)
        for name in SECTIONS:
            if name not in it["sections"]:
                self.error(None, "section `## %s` missing: an evaluated contracts step fills it" % name)
        self.check_signals(it)
        self.check_declared(it)
        return it

    def cite(self, line, row, required, what):
        if required and not row["findings"]:
            self.error(line, "%s needs the finding that says why" % what)
        for fid in row["findings"]:
            if fid not in self.findings:
                self.error(line, "%s cites %s, which is not a finding of this file" % (what, fid))

    def check_signals(self, it):
        expected = {r["sid"]: r for r in signal_rows(self.outputs)}
        seen = {}
        for row in it["signals"]:
            line, sid = row["line"], row["sid"]
            if sid in seen:
                self.error(line, "%s has two rows (also line %d)" % (sid, seen[sid]))
            seen.setdefault(sid, line)
            want = expected.get(sid)
            if want is None:
                self.error(line, "%s is not a signal of this run's detectors" % sid)
            elif "`%s" % want["path"] not in row["cell"]:
                self.error(line, "%s is a signal on `%s`, not what this row names" % (sid, want["path"]))
            if row["judgment"] == UNFILLED:
                self.error(line, "%s: judgment left `?`" % sid)
                continue
            if row["judgment"] not in JUDGMENTS:
                self.error(line, "%s: judgment `%s` not in %s" % (sid, row["judgment"], " | ".join(JUDGMENTS)))
                continue
            self.cite(line, row, row["judgment"] != "minor", "%s (%s)" % (sid, row["judgment"]))
        for sid in expected:
            if sid not in seen:
                self.error(None, "%s has no row in `## Signals`" % sid)

    def check_declared(self, it):
        rows = it["declared"]
        if len(rows) != 1:
            self.error(rows[1]["line"] if len(rows) > 1 else None, "`## Declared` needs exactly one row")
            if not rows:
                return
        row = rows[0]
        line, detected = row["line"], row["detected"]
        if detected == UNFILLED:
            self.error(line, "the detected Door is left `?`")
            return
        if detected not in DOORS:
            self.error(line, "the detected Door `%s` is not one-way or two-way" % detected)
            return
        self.cite(line, row, False, "the declared row")
        one_way = one_way_rows(it)
        if one_way and detected != "one-way":
            self.error(line, "the detected Door is two-way, but %s is judged one-way"
                       % ", ".join(r["sid"] for r in one_way))
        if detected == "one-way" and not one_way and not row["findings"]:
            self.error(line, "the detected Door is one-way, but no signal is judged one-way and the row cites"
                             " no finding that says why")
        declared = declared_door(self.found)
        disagreements = {fid: f for fid, f in self.findings.items()
                         if "declared" in f.data or "detected" in f.data}
        if declared is None:
            for fid, f in sorted(disagreements.items()):
                self.error(f.line, "%s is a disagreement finding, but no Door was declared to disagree with" % fid)
            return
        for fid, f in sorted(disagreements.items()):
            if (str(f.data.get("declared")), str(f.data.get("detected"))) != (declared, detected):
                self.error(f.line, "%s: declared `%s`, detected `%s`, but the PR declares `%s` and the step"
                                   " detected `%s`" % (fid, f.data.get("declared"), f.data.get("detected"),
                                                         declared, detected))
        if declared != detected:
            cited = [fid for fid in row["findings"] if fid in disagreements]
            if not cited:
                self.error(line, "the PR declares a %s Door and the step detected %s: the row cites the"
                                 " disagreement finding, with `declared` and `detected`" % (declared, detected))
        elif disagreements:
            for fid, f in sorted(disagreements.items()):
                self.error(f.line, "%s is a disagreement finding, but the declared and detected Doors agree" % fid)
