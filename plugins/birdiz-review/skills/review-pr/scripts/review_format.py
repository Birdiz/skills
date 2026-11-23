"""The review extension of the finding core, and the run directory it reads.

- Axes `intent` (INT), `contracts` (BRK), `structure` (STR); the extra keys
  `diff`, `attention`, `blocks_merge`, `fan_in`, and `declared` / `detected`
  on a disagreement finding; the prose sections **Evidence.** and
  **Reviewer question.**
- The run directory: `run.json` (the run header), `signals/*.json` (the
  detector outputs), `findings/<axis>.md`, `brief.md` (the brief, a
  projection of the other three).
- The file buckets, the proposed verdict and its round count, and the brief
  drawn from them: `brief.py` writes it, the validator checks it. A file in
  a risk zone of the risk map the header records is never `skim`.
- Where pointers open: the head tree, extracted from git objects into
  `repo-<head short sha>/` in the run directory.
- The sources: `sources.json` and `sources/`, the PR body, spec and tickets
  the run read and how each one fared against the Pocock contract.
"""
import fnmatch
import json
import os
import re

from finding_core import pointers
from finding_core.markdown import blocks, bullets, label_of, paragraphs, parse_yaml, read
from finding_core.validator import CORE_KEYS, Extension
import risk_map

VERSION = "review-pr@0.1.0"

AXES = {"intent": "INT", "contracts": "BRK", "structure": "STR"}
TITLES = {"intent": "Intent", "contracts": "Contracts", "structure": "Structure"}
AREAS = {
    "intent": ["Criteria to hunks", "Files to tickets or criteria", "Out of scope and decisions"],
    "contracts": ["Code API", "Routes and wire contracts", "Persistence", "Configuration",
                  "Behaviour (assertions)", "Fan-in", "Declared vs detected"],
    "structure": ["New files", "Import graph", "Dependencies", "Pattern divergence", "ADRs", "Glossary"],
}
# The steps this version runs; the others get a coverage saying so.
STEPS_IN_VERSION = []
# Review dimensions no version has yet: always printed with the verdict.
LATER = ["gates", "test integrity", "adversarial"]

HEADER = "run.json"
SIGNALS = "signals"
FINDINGS = "findings"
BRIEF = "brief.md"
TREE = "repo-"
HEADER_KEYS = ["schema", "core", "repo", "branch", "target", "base", "head",
               "merge_base", "diff", "started", "tools", "detectors"]
OUTPUT_KEYS = ["detector", "version", "content", "applies_to", "covered", "not_covered", "signals"]

BUCKETS = ["must-read", "glance", "skim", "unproven"]
SECTIONS = ["Declared vs detected", "Must read", "Glance", "Skim", "Unproven", "Coverage gaps", "Verdict"]
BUCKET_SECTION = {"must-read": "Must read", "glance": "Glance", "skim": "Skim", "unproven": "Unproven"}
VERDICTS = ["merge", "fix", "close-and-reprompt"]
VERDICT_LINE = re.compile(r"^Proposed verdict: (%s), round (\d+)(?: \((.+)\))?\.$" % "|".join(VERDICTS))
DIFF = re.compile(r"[0-9a-f]{7,40}\.\.[0-9a-f]{7,40}")
NO_CONTENT = "no content detector reads this file type in this version"
NOTICE = ("<!-- A projection of run.json, signals/ and findings/, written by brief.py."
          " Never edit it: regenerate it. -->")


class RunError(Exception):
    pass


# --- Reading a run directory ------------------------------------------------

def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise RunError("cannot read %s: %s" % (path, e))


class ReviewFinding:
    """A finding as the brief reads it."""

    def __init__(self, path, line, axis, fid, title, data, question):
        self.path, self.line, self.axis, self.fid = path, line, axis, fid
        self.title, self.data, self.question = title, data, question

    def files(self):
        """The paths its locations point at."""
        out = []
        for loc in self.data.get("locations") or []:
            m = pointers.POINTER.search(str(loc))
            path = m.group("path") if m else str(loc).split(":")[0].strip()
            if path and path not in out:
                out.append(path)
        return out

    def first_location(self):
        locs = self.data.get("locations") or []
        return str(locs[0]) if isinstance(locs, list) and locs else ""


def read_findings_file(path, axis):
    """(findings, axis line) of one findings file; lenient, the validator is strict."""
    lines = read(path)
    out, axis_line = [], None
    sections = blocks(lines, 2)
    for name, start, items in sections[1:]:
        if name == "Coverage":
            for _, line, _, _ in items:
                if line is not None and line.startswith("Axis:"):
                    axis_line = line[len("Axis:"):].strip()
        if name != "Findings":
            continue
        end = next((st for _, st, _ in sections if st > start), len(lines))
        for title, s, sub in blocks(lines, 3)[1:]:
            if title is None or not start < s < end:
                continue
            m = re.match(r"^(F-[A-Z0-9]+-\d+)\s+(.*)$", title)
            yaml_body = next((body for _, line, info, body in sub if line is None and info == "yaml"), None)
            if not m or yaml_body is None:
                continue
            data, _ = parse_yaml(yaml_body)
            question = ""
            for _, para in paragraphs(sub):
                if label_of(para) == "Reviewer question":
                    question = para[len("**Reviewer question.**"):].strip()
            out.append(ReviewFinding(path, s + 1, axis, m.group(1), m.group(2).strip(), data, question))
    return out, axis_line


class Run:
    """One run directory, as the brief and the validator read it."""

    def __init__(self, root):
        self.root = root
        self.header = load_json(os.path.join(root, HEADER))
        if not isinstance(self.header, dict):
            raise RunError("%s is not a JSON object" % HEADER)
        self.outputs = {}
        for rel in self.header.get("detectors") or []:
            self.outputs[rel] = load_json(os.path.join(root, rel))
        self.sources = None
        if self.header.get("sources"):
            self.sources = load_json(os.path.join(root, str(self.header["sources"])))
        self.findings, self.coverage = [], {}
        for axis in AXES:
            path = os.path.join(root, FINDINGS, axis + ".md")
            if os.path.exists(path):
                found, line = read_findings_file(path, axis)
                self.findings.extend(found)
                self.coverage[axis] = line

    def changed(self):
        """Every changed file, as the git detector lists them, in order."""
        out = []
        for o in self.outputs.values():
            for f in o.get("files") or []:
                if f.get("path") and f["path"] not in out:
                    out.append(f["path"])
        return out

    def tree(self):
        head = (self.header.get("head") or {}).get("sha", "")
        return os.path.join(self.root, TREE + head[:12])


def axis_status(line):
    """(status word, why) of an axis line, `not-evaluable (why)`."""
    if line is None:
        return "not-evaluable", "no findings file"
    m = re.match(r"([a-z-]+)\s*(?:\((.*)\))?", line)
    return (m.group(1), (m.group(2) or "").strip()) if m else (line, "")


def rounds(root):
    """Distinct head shas among the run directories of the same branch: the
    parent of `root` holds one directory per head, this one included."""
    shas = set()
    branch_dir = os.path.dirname(os.path.abspath(root))
    names = [n for n in os.listdir(branch_dir) if not n.startswith(".")] if os.path.isdir(branch_dir) else []
    for name in names + [os.path.basename(os.path.abspath(root))]:
        path = os.path.join(branch_dir, name, HEADER)
        try:
            sha = (load_json(path).get("head") or {}).get("sha")
        except (RunError, AttributeError):
            continue
        if sha:
            shas.add(sha)
    return max(len(shas), 1)


# --- Buckets ----------------------------------------------------------------

def applies(output, path):
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(os.path.basename(path), p)
               for p in output.get("applies_to") or [])


def not_covered_reason(output, path):
    for item in output.get("not_covered") or []:
        if isinstance(item, dict) and item.get("path") == path:
            return item.get("reason") or "no reason given"
    return "not in its covered files"


def zone_reasons(zones):
    return ["risk zone %s (`%s`)" % (z, g) for z, g in zones]


def bucket_of(path, outputs, findings, zones=()):
    """(bucket, reasons, proof) of one changed file, by the rules in order:
    must-read, unproven, glance, skim. `zones` are the (zone, glob) pairs of
    the risk map it matches: they name a reason in every bucket and keep it
    out of `skim`. `proof` lists the detector outputs a skim rests on."""
    zoned = zone_reasons(zones)
    pointing = [f for f in findings if path in f.files()]
    must = [f for f in pointing if f.data.get("attention") == "must-read"]
    if must:
        return "must-read", [f.fid for f in must] + zoned, []
    content = [(rel, o) for rel, o in sorted(outputs.items()) if o.get("content") is True and applies(o, path)]
    if not content:
        return "unproven", [NO_CONTENT] + zoned, []
    missed = [(rel, o) for rel, o in content if path not in (o.get("covered") or [])]
    if missed:
        return "unproven", ["%s applies but did not cover it: %s" % (rel, not_covered_reason(o, path))
                            for rel, o in missed] + zoned, []
    reasons = []
    for rel, o in sorted(outputs.items()):
        for s in o.get("signals") or []:
            if isinstance(s, dict) and s.get("path") == path:
                reasons.append("%s (%s)" % (s.get("reason") or s.get("kind") or "signal", rel))
    reasons += ["%s %s" % (f.fid, f.title) for f in pointing]
    reasons += zoned
    if reasons:
        return "glance", reasons, []
    return "skim", [], [rel for rel, _ in content]


def risk_rows(run):
    """The (glob, zone) rows of the risk map recorded in the run header."""
    rm = run.header.get("risk_map")
    rows = rm.get("rows") if isinstance(rm, dict) else None
    out = []
    for r in rows or []:
        if isinstance(r, dict) and not risk_map.glob_problem(str(r.get("glob", ""))):
            out.append((r["glob"], str(r.get("zone"))))
    return out


def risk_zones(run):
    """Changed file -> [(zone, glob)] by the risk map in the run header."""
    rows = risk_rows(run)
    return {p: risk_map.zones_for(p, rows) for p in run.changed()} if rows else {}


def buckets(run, zones=None):
    """Changed file -> (bucket, reasons, proof). `zones` defaults to the
    risk map the run header records."""
    zones = risk_zones(run) if zones is None else zones
    return {p: bucket_of(p, run.outputs, run.findings, zones.get(p, ())) for p in run.changed()}


# --- Verdict ----------------------------------------------------------------

def blocking(findings):
    return [f for f in findings if f.data.get("blocks_merge") is True]


def verdict(run, round_no):
    """(verdict, qualifier, reasons)."""
    blocks_ = blocking(run.findings)
    not_run = [(a, axis_status(run.coverage.get(a))) for a in AXES]
    not_run = [(a, why) for a, (status, why) in not_run if status not in ("evaluated", "partial")]
    intent = dict(not_run).get("intent")
    if blocks_ and round_no >= 3:
        word = "close-and-reprompt"
        reasons = ["Round %d, a third distinct head or later, still has merge-blocking findings (%s):"
                   " stop coaching this branch and reprompt." % (round_no, ", ".join(f.fid for f in blocks_))]
    elif blocks_:
        word = "fix"
        reasons = ["Blocks the merge: %s." % ", ".join("%s (%s)" % (f.fid, f.first_location()) for f in blocks_)]
    else:
        word = "merge"
        reasons = ["No finding blocks the merge."]
    parts = []
    others = [a for a, _ in not_run if a != "intent"] + LATER
    if intent is not None:
        parts.append("intent not checked: %s" % (intent or "not evaluated"))
        parts.append("%s not run" % ", ".join(others))
    else:
        parts.append("attention map only: %s not run" % ", ".join(others))
    return word, "; ".join(parts), reasons


# --- The brief ----------------------------------------------------------------

def render_brief(run, zones=None):
    """The brief, from the run header, the detector outputs and the findings."""
    h = run.header
    placed = buckets(run, zones)
    round_no = rounds(run.root)
    word, qualifier, reasons = verdict(run, round_no)
    out = ["# Review brief", "", NOTICE, "",
           "repo: %s, branch: %s, target: %s, diff: %s" % (h.get("repo"), h.get("branch"), h.get("target"), h.get("diff")),
           ""]

    out += ["## Declared vs detected", ""]
    out += declared_lines(run)
    out.append("")

    for bucket in BUCKETS:
        out += ["## %s" % BUCKET_SECTION[bucket], ""]
        files = [p for p in run.changed() if placed[p][0] == bucket]
        if not files:
            out += ["None.", ""]
            continue
        for path in files:
            _, reasons_, proof = placed[path]
            if bucket == "must-read":
                zoned = [r for r in reasons_ if r.startswith("risk zone ")]
                out.append("- `%s`%s" % (path, ": %s." % "; ".join(zoned) if zoned else ""))
                for f in run.findings:
                    if f.fid in reasons_ and path in f.files():
                        q = " **Question:** %s" % f.question if f.question else ""
                        out.append("  - %s `%s`: %s.%s" % (f.fid, f.first_location(), f.title.rstrip("."), q))
            elif bucket == "skim":
                out.append("- `%s`: covered by %s, with no signal; no finding points at it; outside the risk map."
                           % (path, ", ".join(proof)))
            else:
                out.append("- `%s`: %s." % (path, "; ".join(reasons_)))
        out.append("")

    out += ["## Coverage gaps", ""]
    for axis, code in AXES.items():
        status, why = axis_status(run.coverage.get(axis))
        if status != "evaluated":
            out.append("- %s (`%s`): %s%s." % (axis, code, "not run" if status == "not-evaluable" else status,
                                              " (%s)" % why if why else ""))
    out.append("- %s: not in this version." % ", ".join(LATER))
    content = sorted(rel for rel, o in run.outputs.items() if o.get("content") is True)
    if content:
        out.append("- Content detectors run: %s." % ", ".join(content))
    else:
        out.append("- No content detector in this version: every changed file is unproven,"
                   " unless a finding marks it must-read.")
    for rel, o in sorted(run.outputs.items()):
        for item in o.get("not_covered") or []:
            if isinstance(item, dict):
                out.append("- %s did not cover `%s`: %s." % (rel, item.get("path"), item.get("reason")))
    for line in sources_lines(run.sources):
        out.append("- %s" % line)
    out.append("- %s" % risk_map_line(h.get("risk_map")))
    tools = h.get("tools") or []
    found = ["%s %s" % (t.get("name"), t.get("version")) for t in tools if t.get("found")]
    absent = [t.get("name") for t in tools if not t.get("found")]
    out.append("- Tools found on this machine: %s%s." % (", ".join(found) or "none",
                                                         "; not found: %s" % ", ".join(absent) if absent else ""))
    out.append("- Findings stay `unverified`: no verifier in this version, the reader of this brief is the verifier.")
    out.append("")

    out += ["## Verdict", "", "Proposed verdict: %s, round %d (%s)." % (word, round_no, qualifier), ""]
    counts = {b: sum(1 for v in placed.values() if v[0] == b) for b in BUCKETS}
    for r in reasons + ["Files: %s." % ", ".join("%s %d" % (b, counts[b]) for b in BUCKETS)]:
        out.append("- %s" % r)
    return "\n".join(out) + "\n"


def declared_lines(run):
    """The Declared vs detected section: the PR's `Merge Danger`, then each
    disagreement finding."""
    pr = (run.sources or {}).get("pr") if isinstance(run.sources, dict) else None
    disagreements = [f for f in run.findings if "declared" in f.data or "detected" in f.data]
    out = []
    if not isinstance(pr, dict):
        if not disagreements:
            out.append("Risk not declared: no PR body was read (the target is a branch or a range).")
    elif pr.get("status") == "not declared":
        out.append("Risk not declared: the body of PR #%s has no `Merge Danger` section." % pr.get("number"))
    elif pr.get("status") == "declared":
        out.append("Declared in PR #%s: Door `%s`, Blast Radius `%s`." % (
            pr.get("number"), pr.get("door"), pr.get("blast_radius")))
    else:
        out.append("Declared risk not read: PR #%s body, contract drift: %s." % (
            pr.get("number"), "; ".join(pr.get("drift") or [])))
    for f in disagreements:
        out.append("- %s declared `%s`, detected `%s`: %s (%s)" % (
            f.fid, f.data.get("declared"), f.data.get("detected"), f.title, f.first_location()))
    if isinstance(pr, dict) and pr.get("status") == "declared" and not disagreements:
        status, _ = axis_status(run.coverage.get("contracts"))
        if status in ("evaluated", "partial"):
            out.append("No disagreement between the declared risk and what was detected.")
        else:
            out.append("Not compared: the contracts step, which detects it, did not run.")
    return out


def sources_lines(found):
    """The lines on the spec, the tickets and the Pocock contract, for the
    brief's coverage gaps and the run's summary."""
    if not isinstance(found, dict):
        return ["Spec and tickets: not looked for in this run."]
    arts = [a for a in found.get("artifacts") or [] if isinstance(a, dict)]

    def label(a):
        state = {"ok": "", "drift": ", contract drift", "unreadable": ", not read"}.get(a.get("status"), "")
        return "%s%s" % (a.get("ref"), state)

    out = []
    spec = [a for a in arts if a.get("scope") == "spec"]
    scope = [a for a in arts if a.get("scope") == "in scope"]
    siblings = [a for a in arts if a.get("scope") == "sibling"]
    if found.get("found_by") is None:
        line = "Spec and tickets: none found (PR closing references, commit references, spec files named after the branch)"
    else:
        parts = []
        if spec:
            parts.append("spec %s" % label(spec[0]))
            if spec[0].get("tickets_by"):
                parts[-1] += " (tickets by %s)" % spec[0]["tickets_by"]
        if scope:
            parts.append("in scope %s" % ", ".join(label(a) for a in scope))
        if siblings:
            parts.append("%d sibling ticket(s)" % len(siblings))
        line = "Spec and tickets: %s%s" % (found["found_by"], ": %s" % "; ".join(parts) if parts else "")
    out.append(line + ".")
    out.append("Intent sources: %s." % ((found.get("dimensions") or {}).get("intent") or "unknown"))
    for a in arts:
        if a.get("status") == "drift" and a.get("scope") == "sibling":
            out.append("%s (sibling ticket): contract drift: %s." % (a.get("ref"), ", ".join(a.get("drift") or [])))
        elif a.get("status") == "unreadable":
            out.append("%s: not read: %s." % (a.get("ref"), a.get("why")))
    t = found.get("tracker") or {}
    if t.get("status") != "ok":
        out.append("Tracker doc `%s` at the base: %s, %s." % (t.get("path"), t.get("status"), t.get("detail")))
    for note in found.get("notes") or []:
        out.append("Sources: %s." % note)
    out.append("Pocock artifacts checked against %s." % found.get("contract"))
    return out


def risk_map_line(rm):
    """The brief's line on the risk map the run header records."""
    if not isinstance(rm, dict):
        return "Risk map: not read, so no file is placed by risk zone."
    where = "`%s` at the base (%s)" % (rm.get("path"), str(rm.get("sha", ""))[:12])
    if not rm.get("found"):
        return ("Risk map: no %s, so no file is placed by risk zone; run `review-setup` and merge"
                " its `review.md` into the base." % where)
    rows = rm.get("rows") or []
    line = "Risk map: %s, %d glob(s) in %d zone(s)" % (
        where, len(rows), len({r.get("zone") for r in rows if isinstance(r, dict)}))
    problems = rm.get("problems") or []
    if problems:
        line += "; left out: %s" % "; ".join(
            ("line %s: %s" % (p.get("line"), p.get("message"))) if p.get("line") else str(p.get("message"))
            for p in problems if isinstance(p, dict))
    return line + "."


def parse_brief(path):
    """{section: (start line, items)} and the bucket of each listed file:
    [(path, bucket, line, text)]."""
    lines = read(path)
    sections = {name: (start, items) for name, start, items in blocks(lines, 2)[1:]}
    listed = []
    for bucket in BUCKETS:
        if BUCKET_SECTION[bucket] not in sections:
            continue
        for i, text in bullets(sections[BUCKET_SECTION[bucket]][1]):
            m = re.match(r"^[-*]\s+`([^`]+)`", text)
            listed.append((m.group(1) if m else None, bucket, i + 1, text))
    return lines, sections, listed


# --- The extension ----------------------------------------------------------

class ReviewExtension(Extension):
    name = VERSION
    schema = "review-pr"
    findings_dir = FINDINGS
    axes = AXES
    keys = CORE_KEYS + ["diff", "attention", "blocks_merge", "fan_in"]
    optional = ["declared", "detected"]
    enums = {"attention": ["must-read", "glance"]}
    prose = ["Evidence", "Reviewer question"]
    verify_step = "verification"
    requirable = {"brief": "brief"}

    def __init__(self, rep, root):
        super().__init__(rep, root)
        self.run = None
        try:
            self.run = Run(root)
        except RunError as e:
            rep.error(os.path.join(root, HEADER), None, str(e))
            return
        self.check_header()

    def check_header(self):
        rep, h, path = self.rep, self.run.header, os.path.join(self.root, HEADER)
        for k in HEADER_KEYS:
            if k not in h:
                rep.error(path, None, "key `%s` missing" % k)
        if "diff" in h and not DIFF.fullmatch(str(h["diff"])):
            rep.error(path, None, "diff `%s` is not `<base sha>..<head sha>`" % h["diff"])
        for k in ("base", "head"):
            if k in h and not (isinstance(h[k], dict) and re.fullmatch(r"[0-9a-f]{40,64}", str(h[k].get("sha", "")))):
                rep.error(path, None, "%s must be {ref, sha} with a full sha" % k)
        head = str((h.get("head") or {}).get("sha", "")) if isinstance(h.get("head"), dict) else ""
        if head and os.path.basename(os.path.normpath(self.root)) != head[:12]:
            rep.error(path, None, "the run directory is not named after the head short sha %s" % head[:12])
        tools = h.get("tools")
        if not isinstance(tools, list) or not any(isinstance(t, dict) and t.get("name") == "git" for t in tools):
            rep.error(path, None, "tools must list every detector tool looked for, git included")
        else:
            for t in tools:
                if not isinstance(t, dict) or not isinstance(t.get("found"), bool) or (t.get("found") and not t.get("version")):
                    rep.error(path, None, "tool %r: needs `name`, `found` and, when found, `version`" % (t,))
        for rel, o in sorted(self.run.outputs.items()):
            opath = os.path.join(self.root, rel)
            if not rel.startswith(SIGNALS + "/"):
                rep.error(path, None, "detector output %s is not under %s/" % (rel, SIGNALS))
            if not isinstance(o, dict):
                rep.error(opath, None, "not a JSON object")
                continue
            for k in OUTPUT_KEYS:
                if k not in o:
                    rep.error(opath, None, "key `%s` missing" % k)
            if not isinstance(o.get("content"), bool):
                rep.error(opath, None, "content must be true or false")
        found = self.run.sources
        if h.get("sources") is not None:
            spath = os.path.join(self.root, str(h["sources"]))
            if not isinstance(found, dict):
                rep.error(spath, None, "not a JSON object")
            else:
                for k in ("contract", "found_by", "tracker", "artifacts", "dimensions"):
                    if k not in found:
                        rep.error(spath, None, "key `%s` missing" % k)
                for a in found.get("artifacts") or []:
                    if not isinstance(a, dict) or a.get("status") not in ("ok", "drift", "unreadable"):
                        rep.error(spath, None, "artifact %r: status must be ok, drift or unreadable" % (a,))
                    elif a.get("status") != "unreadable" and not os.path.isfile(os.path.join(self.root, str(a.get("file")))):
                        rep.error(spath, None, "artifact %s: its copy %s is missing" % (a.get("ref"), a.get("file")))
                    elif a.get("status") == "drift" and not a.get("drift"):
                        rep.error(spath, None, "artifact %s: drift without saying what" % a.get("ref"))
                intent = str((found.get("dimensions") or {}).get("intent"))
                if not (intent == "evaluable" or intent.startswith("not-evaluable (")):
                    rep.error(spath, None, "intent dimension `%s` is not `evaluable` or `not-evaluable (<why>)`" % intent)
        if not self.run.changed():
            rep.error(path, None, "no detector output lists the changed files: an empty diff is refused, never reviewed")

    def check_keys(self, f):
        rep, path, yi, fid, data = self.rep, f.path, f.yi, f.fid, f.data
        diff = str(data.get("diff", ""))
        if "diff" in data and not DIFF.fullmatch(diff):
            rep.error(path, yi + 1, "%s: diff `%s` is not `<base sha>..<head sha>`" % (fid, diff))
        elif "diff" in data and self.run and diff != self.run.header.get("diff"):
            rep.error(path, yi + 1, "%s: diff %s is not this run's %s" % (fid, diff, self.run.header.get("diff")))
        if "blocks_merge" in data and not isinstance(data["blocks_merge"], bool):
            rep.error(path, yi + 1, "%s: blocks_merge must be true or false" % fid)
        if "fan_in" in data and not re.fullmatch(r"\d+|unknown", str(data["fan_in"])):
            rep.error(path, yi + 1, "%s: fan_in `%s` is not a count or `unknown`" % (fid, data["fan_in"]))
        if ("declared" in data) != ("detected" in data):
            rep.error(path, yi + 1, "%s: a disagreement finding gives both `declared` and `detected`" % fid)
        if data.get("status") not in (None, "unverified"):
            rep.error(path, yi + 1, "%s: status %s, but no verifier exists in this version: it stays unverified"
                      % (fid, data.get("status")))

    def finish(self, findings, ids):
        if self.run is None:
            return ""
        rep, run = self.rep, self.run
        path = os.path.join(self.root, BRIEF)
        if not os.path.exists(path):
            rep.error(path, None, "no brief: run brief.py")
            return ""
        lines, sections, listed = parse_brief(path)
        names = [n for n, _, _ in blocks(lines, 2)[1:]]
        for name in SECTIONS:
            if name not in names:
                rep.error(path, None, "section `## %s` missing" % name)
        known = [n for n in names if n in SECTIONS]
        if known != sorted(known, key=SECTIONS.index) or len(set(known)) != len(known):
            rep.error(path, None, "sections out of order or repeated: %s" % ", ".join(known))

        changed = run.changed()
        where = {}
        for p, bucket, line, text in listed:
            if p is None:
                rep.error(path, line, "bucket entry without a `path`: %s" % text[:60])
                continue
            if p not in changed:
                rep.error(path, line, "`%s` is in %s but is not a changed file" % (p, bucket))
            if p in where:
                rep.error(path, line, "`%s` is in %s and in %s: one bucket per file" % (p, where[p][0], bucket))
            where.setdefault(p, (bucket, line, text))
        for p in changed:
            if p not in where:
                rep.error(path, None, "changed file `%s` is in no bucket" % p)
        for p, (bucket, line, text) in sorted(where.items()):
            if bucket == "skim":
                self.check_skim(path, line, p, text)
            if bucket == "must-read" and not any(p in f.files() and f.data.get("attention") == "must-read"
                                                 for f in run.findings):
                rep.error(path, line, "`%s` is must-read, but no finding with `attention: must-read` points at it" % p)

        verdicts = [(i, line) for i, line in enumerate(lines) if line.startswith("Proposed verdict:")]
        start = sections.get("Verdict", (None,))[0]
        good = [(i, line) for i, line in verdicts if VERDICT_LINE.match(line) and start is not None and i > start]
        if len(verdicts) != 1 or not good:
            rep.error(path, verdicts[0][0] + 1 if verdicts else None,
                      "the Verdict section needs one `Proposed verdict: <merge|fix|close-and-reprompt>, round <n> (<not run>).` line")
        if render_brief(run) != "\n".join(lines):
            rep.pending("brief", path, None, "not the projection of run.json, signals/ and findings/ as they are now: run brief.py")

        placed = buckets(run)
        counts = {b: sum(1 for v in placed.values() if v[0] == b) for b in BUCKETS}
        return ", %d changed files (%s), round %d" % (
            len(changed), ", ".join("%s %d" % (b, counts[b]) for b in BUCKETS), rounds(self.root))

    def check_skim(self, path, line, p, text):
        """Invariant: skim rests on detector evidence, never on the model."""
        rep, run = self.rep, self.run
        cited = re.findall(r"%s/[\w.-]+\.json" % SIGNALS, text)
        content = [rel for rel, o in run.outputs.items() if o.get("content") is True and applies(o, p)]
        if not content:
            rep.error(path, line, "`%s` is skim, but no content detector reads its file type: it is unproven" % p)
        if not cited:
            rep.error(path, line, "`%s` is skim without the detector outputs that prove it" % p)
        for rel in cited:
            o = run.outputs.get(rel)
            if o is None:
                rep.error(path, line, "`%s` is skim on %s, which is not a detector output of this run" % (p, rel))
            elif o.get("content") is not True or p not in (o.get("covered") or []):
                rep.error(path, line, "`%s` is skim on %s, which is not a content detector that covered it" % (p, rel))
        for rel in content:
            if p not in (run.outputs[rel].get("covered") or []):
                rep.error(path, line, "`%s` is skim, but %s applies to it and did not cover it" % (p, rel))
        for rel, o in sorted(run.outputs.items()):
            if any(isinstance(s, dict) and s.get("path") == p for s in o.get("signals") or []):
                rep.error(path, line, "`%s` is skim, but %s signalled on it" % (p, rel))
        for f in run.findings:
            if p in f.files():
                rep.error(path, line, "`%s` is skim, but %s points at it" % (p, f.fid))
        for zone, glob in risk_map.zones_for(p, risk_rows(run)):
            rep.error(path, line, "`%s` is skim, but it is in risk zone %s (`%s`)" % (p, zone, glob))


# --- Pointers ---------------------------------------------------------------

class ReviewLayout(pointers.Layout):
    """The findings files, read against the head tree of the run."""

    name = VERSION
    empty = "no findings file in %s"
    folders = (SIGNALS,)
    clones = TREE

    def files(self):
        d = os.path.join(self.root, FINDINGS)
        if not os.path.isdir(d):
            return []
        return sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith(".md"))

    def roots(self):
        roots = [self.repo] if self.repo else []
        try:
            head = (load_json(os.path.join(self.root, HEADER)).get("head") or {}).get("sha", "")
        except (RunError, AttributeError):
            head = ""
        if head:
            roots.append(os.path.join(self.root, TREE + head[:12]))
        roots.append(self.root)
        return list(dict.fromkeys(os.path.normpath(r) for r in roots))


# --- Placeholders for the steps not in this version -------------------------

def coverage_not_run(axis, why="step not in this version"):
    """A findings file for a step that did not run: its coverage says so."""
    rows = ["| %s | not-evaluable | %s. |" % (area, why[0].upper() + why[1:]) for area in AREAS[axis]]
    return "\n".join([
        "# %s" % TITLES[axis], "",
        "## Coverage", "",
        "skill: %s, tools: []" % VERSION, "",
        "| Area | Status | Notes |", "|---|---|---|"] + rows + [
        "", "Axis: not-evaluable (%s)" % why, "",
        "## Findings", "", "None.", "",
        "## Leads", "", "None.", ""])
