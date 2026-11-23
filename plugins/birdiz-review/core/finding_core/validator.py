"""The finding schema core and the validator engine that reads it.

The core owns what a finding means in every plugin: a heading and an ID
`F-<AXIS>-<NNN>`, a YAML block with the core keys, a status a verifier owns
(`verification` and its **Verification.** note), severity and confidence,
`sensitive` and `promptable` as booleans, a text hash a verification vouches
for, leads `L-<AXIS>-<NN>` with a status, the coverage table's area statuses,
and IDs cited that resolve.

A plugin's `Extension` adds the rest: its axes, its extra keys and values,
its prose sections, its `##` sections and their order, its own sections'
checks, and what it checks once every findings file is read.
"""
import hashlib
import os
import re
import sys

from . import NAME
from .markdown import blocks, bullets, label_of, paragraphs, parse_yaml, read, strip_comment
from .report import Report

SEVERITIES = ["info", "low", "medium", "high", "critical"]
CORE_KEYS = ["id", "axis", "status", "severity", "confidence", "sensitive", "promptable", "locations"]
CORE_OPTIONAL = ["verification"]
CORE_ENUMS = {
    "status": ["unverified", "confirmed", "refuted"],
    "severity": SEVERITIES,
    "confidence": ["high", "medium", "low"],
}
VERIFIERS = ["sub-agent", "new session"]
AREA_STATUSES = ["evaluated", "partial", "not-evaluable", "not-requested"]
LEAD_STATUSES = r"(promoted to F-|closed:|open:)"
SHA = re.compile(r"[0-9a-f]{12}")
DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def id_pattern(prefix, codes):
    """`<prefix>-<axis code>-<digits>` for the given axis codes."""
    alt = "|".join(sorted(codes, key=len, reverse=True))
    return re.compile(r"\b%s-(%s)-(\d+)\b" % (prefix, alt))


class Extension:
    """What a plugin adds to the core. One instance per run, built on the
    run's report and workspace root before any findings file is read."""

    name = "finding-core"        # the plugin's schema, with its version
    schema = "finding-core"      # the name messages give the schema
    findings_dir = "findings"    # one `<axis>.md` per axis
    axes = {}                    # axis name -> ID code
    keys = CORE_KEYS             # every required key, in schema order
    optional = []                # keys allowed beyond `verification`
    legacy = []                  # keys of older versions, accepted silently
    enums = {}                   # the extension's keys with a closed set of values
    prose = []                   # labelled prose sections, in order, before **Verification.**
    trailing = []                # labels allowed after **Verification.** only
    sections = ["Coverage", "Findings", "Leads"]
    required_sections = ["Coverage", "Findings", "Leads"]
    id_prefixes = ["F", "L"]     # ID kinds collected and resolved across files
    lead_links = ["promoted to", "settled by"]
    verify_step = "verify-findings"
    requirable = {}              # --require word -> step whose pending lines become errors

    def __init__(self, rep, root):
        self.rep, self.root = rep, root

    @classmethod
    def label(cls):
        return "%s (%s)" % (cls.name, NAME)

    def check_keys(self, f):
        """The extension's own keys, after the core's."""

    def check_prose(self, f):
        """The extension's own prose rules; returns more dates the finding
        carries (answers, checks), for checks made once all files are read."""
        return []

    def check_lead(self, path, line, lid, axis, last):
        """A lead whose last status is `last`, after the core's checks."""

    def check_section(self, name, path, axis, start, items, sections, lines, ids, refs):
        """A `##` section the core does not own."""

    def finish(self, findings, ids):
        """After every findings file; returns the summary's tail."""
        return ""


class Finding:
    """One finding as read: the core's view, which extensions read and extend."""

    def __init__(self, path, line, data, labels, text):
        self.path, self.line, self.data, self.labels, self.text = path, line, data, labels, text
        self.dates = []
        self.sha = None
        self.unstamped = False


def fingerprint(title, yaml_body, items):
    """Hash of what a verification vouches for: the heading, the YAML but its
    `status` and `verification` keys, the prose but the verification note.
    Spacing is ignored, so rewrapping a paragraph changes nothing."""
    parts = [title]
    for raw in yaml_body:
        line = strip_comment(raw).strip()
        if line and not re.match(r"(status|verification)\s*:", line):
            parts.append(line)
    in_note = False
    for _, line, _, body in items:
        if line is not None and label_of(line.strip()):
            in_note = label_of(line.strip()) == "Verification"
        if not in_note:
            parts.extend(body if line is None else [line])
    text = " ".join(" ".join(parts).split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class Reading:
    """A finding while it is checked: what the extension's hooks need."""

    def __init__(self, path, axis, fid, start, yi, data):
        self.path, self.axis, self.fid, self.start, self.yi, self.data = path, axis, fid, start, yi, data
        self.ver = None
        self.paras, self.labels, self.names, self.text = [], [], [], ""


def check_finding(rep, ext, path, axis, title, start, items):
    code = ext.axes[axis]
    m = re.match(r"^(F-[A-Z0-9]+-\d+)\s+\S", title)
    if not m:
        rep.error(path, start + 1, "finding heading is not `### F-<AXIS>-<NNN> <title>`: %s" % title)
        return None
    fid = m.group(1)
    if not re.fullmatch(r"F-%s-\d{3}" % code, fid):
        rep.error(path, start + 1, "%s: ID does not follow F-%s-<NNN> for this file" % (fid, code))
    yaml_blocks = [(i, body) for i, line, info, body in items if line is None and info == "yaml"]
    first = next(((i, line, info) for i, line, info, _ in items if line is None or line.strip()), None)
    if not yaml_blocks or first is None or first[1] is not None or first[2] != "yaml":
        rep.error(path, start + 1, "%s: no YAML block right after the heading" % fid)
        return None
    yi, body = yaml_blocks[0]
    data, problems = parse_yaml(body)
    f = Reading(path, axis, fid, start, yi, data)
    for off, msg in problems:
        rep.error(path, yi + 2 + off, "%s: %s" % (fid, msg))
    for k in ext.keys:
        if k not in data:
            rep.error(path, yi + 1, "%s: key `%s` missing" % (fid, k))
    for k in data:
        if k not in ext.keys + CORE_OPTIONAL + ext.optional + ext.legacy:
            rep.warn(path, yi + 1, "%s: key `%s` is not in the schema" % (fid, k))
    enums = dict(CORE_ENUMS)
    enums.update(ext.enums)
    for k, allowed in enums.items():
        if k in data and data[k] not in allowed:
            rep.error(path, yi + 1, "%s: %s `%s` not in %s" % (fid, k, data[k], " | ".join(allowed)))
    for k in ("sensitive", "promptable"):
        if k in data and not isinstance(data[k], bool):
            rep.error(path, yi + 1, "%s: %s must be true or false" % (fid, k))
    if data.get("id") not in (None, fid):
        rep.error(path, yi + 1, "%s: id `%s` differs from the heading" % (fid, data["id"]))
    if data.get("axis") not in (None, axis):
        rep.error(path, yi + 1, "%s: axis `%s` in the %s file" % (fid, data["axis"], axis))
    if "locations" in data and (not isinstance(data["locations"], list) or not data["locations"]):
        rep.error(path, yi + 1, "%s: locations must be a non-empty list" % fid)
    ext.check_keys(f)

    ver = data.get("verification")
    if ver is not None:
        if not isinstance(ver, dict) or set(ver) - {"sha"} != {"by", "on"}:
            rep.error(path, yi + 1, "%s: verification must be {by: <who>, on: <YYYY-MM-DD>, sha: <hash>}" % fid)
            ver = None
        else:
            if ver["by"] not in VERIFIERS:
                rep.error(path, yi + 1, "%s: verification by `%s` not in %s" % (fid, ver["by"], " | ".join(VERIFIERS)))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(ver["on"])):
                rep.error(path, yi + 1, "%s: verification on `%s` is not a date" % (fid, ver["on"]))
            if "sha" in ver and not SHA.fullmatch(str(ver["sha"])):
                rep.error(path, yi + 1, "%s: verification sha `%s` is not a 12-character hash" % (fid, ver["sha"]))
    f.ver = ver

    rest = [it for it in items if it[0] > yi]
    sha = fingerprint(title, body, rest)
    if ver is not None and "sha" in ver and SHA.fullmatch(str(ver["sha"])) and ver["sha"] != sha:
        rep.pending(ext.verify_step, path, start + 1,
                    "%s: text changed since its verification (sha %s, now %s)" % (fid, ver["sha"], sha))
    paras = paragraphs(rest)
    labels = [(i, label_of(p), p) for i, p in paras if label_of(p)]
    names = [l for _, l, _ in labels]
    for name in ext.prose:
        n = names.count(name)
        if n == 0:
            rep.error(path, start + 1, "%s: **%s.** missing" % (fid, name))
        elif n > 1:
            rep.error(path, start + 1, "%s: **%s.** given %d times" % (fid, name, n))
    order = [n for n in names if n in ext.prose + ["Verification"] + ext.trailing]
    expected = [n for n in ext.prose + ["Verification"] if n in order]
    seen = [n for n in order if n not in ext.trailing]
    dedup = [n for k, n in enumerate(seen) if n not in seen[:k]]
    if dedup != expected:
        rep.error(path, start + 1, "%s: prose sections out of order (%s)" % (fid, ", ".join(dedup)))
    for name in ext.trailing:
        if name in names and "Verification" in names and names.index(name) < names.index("Verification"):
            rep.error(path, start + 1, "%s: **%s.** comes before **Verification.**" % (fid, name))

    status = data.get("status")
    has_note = "Verification" in names
    if status in ("confirmed", "refuted") and ver is None and "verification" not in data:
        rep.error(path, yi + 1, "%s: status %s without a `verification` key" % (fid, status))
    if status in ("confirmed", "refuted") and not has_note:
        rep.error(path, start + 1, "%s: status %s without a **Verification.** note" % (fid, status))
    if "verification" in data and not has_note:
        rep.error(path, start + 1, "%s: `verification` key without a **Verification.** note" % fid)
    if has_note and "verification" not in data:
        rep.error(path, yi + 1, "%s: **Verification.** note without a `verification` key" % fid)
    if status == "unverified" and "verification" not in data:
        rep.pending(ext.verify_step, path, start + 1, "%s: not verified yet" % fid)
    f.paras, f.labels, f.names = paras, labels, names
    f.text = " ".join(p for _, p in paras)
    dates = ext.check_prose(f)
    finding = Finding(path, start + 1, data, names, f.text)
    finding.dates = list(dates) + ([str(ver["on"])] if ver is not None else [])
    finding.sha = sha
    finding.unstamped = ver is not None and "sha" not in ver
    return finding


def check_leads(rep, ext, path, axis, items, ids, refs):
    code = ext.axes[axis]
    links = re.compile(r"(?:%s)\s+(F-[A-Z0-9]+-\d+)" % "|".join(ext.lead_links))
    for i, text in bullets(items):
        m = re.match(r"^[-*]\s+\*\*(L-[A-Z0-9]+-\d+)\b", text)
        if not m:
            rep.error(path, i + 1, "lead bullet without `**L-%s-<NN> <title>.**`: %s" % (code, text[:60]))
            continue
        lid = m.group(1)
        if not re.fullmatch(r"L-%s-\d{2,}" % code, lid):
            rep.error(path, i + 1, "%s: ID does not follow L-%s-<NN> for this file" % (lid, code))
        if lid in ids["L"]:
            rep.error(path, i + 1, "%s: ID used twice (also %s)" % (lid, ids["L"][lid]))
        ids["L"][lid] = "%s:%d" % (os.path.relpath(path, rep.root), i + 1)
        statuses = list(re.finditer(LEAD_STATUSES, text))
        if not statuses:
            rep.error(path, i + 1, "%s: no status (`promoted to F-…`, `closed:`, `open:`)" % lid)
            continue
        last = text[statuses[-1].start():]
        for m2 in links.finditer(text):
            refs.append((path, i + 1, lid, m2.group(1), "error"))
        ext.check_lead(path, i + 1, lid, axis, last)


def check_coverage(rep, path, start, items):
    prose = [line for _, line, _, _ in items if line is not None and line.strip()]
    if not prose:
        rep.error(path, start + 1, "coverage is empty")
        return
    if not any(re.search(r"\bskill:\s*[a-z-]+@\d", line) for line in prose[:5]):
        rep.warn(path, start + 1, "coverage does not open with `skill: <name>@<version>` (older skills)")
    header, col = None, None
    for i, line, _, _ in items:
        if line is None or not line.startswith("|"):
            header, col = None, None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            col = cells.index("Status") if "Status" in cells and cells and cells[0] == "Area" else None
            continue
        if col is None or set("".join(cells)) <= set("-: "):
            continue
        word = re.match(r"[a-z-]*", cells[col] if col < len(cells) else "").group(0)
        if word not in AREA_STATUSES:
            rep.error(path, i + 1, "area `%s`: status `%s` not in %s" % (cells[0], cells[col] if col < len(cells) else "", " | ".join(AREA_STATUSES)))


def check_findings_file(rep, ext, path, axis, ids, refs, findings):
    lines = read(path)
    sections = blocks(lines, 2)
    names = [h for h, _, _ in sections[1:]]
    for name in names:
        if name not in ext.sections:
            rep.warn(path, None, "section `## %s` is not in %s" % (name, ext.schema))
    for name in ext.required_sections:
        if name not in names:
            rep.error(path, None, "section `## %s` missing" % name)
    known = [n for n in names if n in ext.sections]
    if known != sorted(known, key=ext.sections.index) or len(set(known)) != len(known):
        rep.error(path, None, "sections out of order or repeated: %s" % ", ".join(known))
    for name, start, items in sections[1:]:
        if name == "Coverage":
            check_coverage(rep, path, start, items)
        elif name == "Findings":
            end = next((st for _, st, _ in sections if st > start), len(lines))
            for title, s, sub in blocks(lines, 3)[1:]:
                if title is None or not start < s < end:
                    continue
                f = check_finding(rep, ext, path, axis, title, s, sub)
                if f is None:
                    continue
                fid = f.data.get("id") or title.split()[0]
                if fid in ids["F"]:
                    rep.error(path, s + 1, "%s: ID used twice (also %s)" % (fid, ids["F"][fid]))
                ids["F"][fid] = "%s:%d" % (os.path.relpath(path, rep.root), s + 1)
                findings[fid] = f
        elif name == "Leads":
            check_leads(rep, ext, path, axis, items, ids, refs)
        elif name in ext.sections:
            ext.check_section(name, path, axis, start, items, sections[1:], lines, ids, refs)
    text = "\n".join(lines)
    for prefix in ext.id_prefixes:
        for m in id_pattern(prefix, ext.axes.values()).finditer(text):
            refs.append((path, text.count("\n", 0, m.start()) + 1, None, m.group(0), "warning"))


def main(argv, extension, doc):
    """The validator's command line, for a plugin's `Extension` class;
    `doc` is the usage --help prints."""
    args = argv[1:]
    require = set()
    root = None
    prints = None
    while args:
        a = args.pop(0)
        if a == "--require" and args:
            require.add(args.pop(0))
        elif a == "--fingerprint":
            prints = []
        elif a in ("-h", "--help"):
            print(doc)
            return 0
        elif a == "--version":
            print(extension.label())
            return 0
        elif root is None and not a.startswith("-"):
            root = a
        elif prints is not None and not a.startswith("-"):
            prints.append(a)
        else:
            print("unknown argument: %s" % a, file=sys.stderr)
            return 2
    if root is None or not require <= set(extension.requirable):
        print(doc, file=sys.stderr)
        return 2
    fdir = os.path.join(root, extension.findings_dir)
    if not os.path.isdir(fdir):
        print("no %s/ directory in %s" % (extension.findings_dir, root), file=sys.stderr)
        return 2

    rep = Report(root)
    ext = extension(rep, root)
    ids = {p: {} for p in ext.id_prefixes}
    refs, findings = [], {}
    for name in sorted(os.listdir(fdir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(fdir, name)
        axis = name[:-3]
        if axis not in ext.axes:
            rep.error(path, None, "`%s` is not an axis of %s" % (axis, ext.schema))
            continue
        check_findings_file(rep, ext, path, axis, ids, refs, findings)

    if prints is not None:
        for fid in prints or sorted(findings):
            if fid not in findings:
                print("%s: no such finding" % fid, file=sys.stderr)
                return 2
            print("%s %s" % (fid, findings[fid].sha))
        return 0

    unstamped = sorted(fid for fid, f in findings.items() if f.unstamped)
    if unstamped:
        rep.warn(fdir, None, "%d verified findings without `sha` (older skills): a text changed the day of its verification does not show (%s to %s)"
                 % (len(unstamped), unstamped[0], unstamped[-1]))

    known = set().union(*(set(ids[p]) for p in ext.id_prefixes))
    seen = set()
    for path, line, owner, target, level in refs:
        if target in known or (path, target, level) in seen:
            continue
        seen.add((path, target, level))
        if level == "error":
            rep.error(path, line, "%s points to %s, which does not exist" % (owner, target))
        else:
            rep.warn(path, line, "%s is cited but defined nowhere in %s/" % (target, ext.findings_dir))

    tail = ext.finish(findings, ids)

    required = {ext.requirable[w] for w in require}
    for kind, step, text in rep.lines:
        if kind == "PENDING" and step in required:
            text = text.replace("PENDING", "ERROR  ", 1)
            rep.counts["PENDING"] -= 1
            rep.counts["ERROR"] += 1
        print(text)

    statuses = {}
    for f in findings.values():
        statuses[f.data.get("status")] = statuses.get(f.data.get("status"), 0) + 1
    print("%s: %d findings (%s), %d leads%s" % (
        ext.label(), len(findings),
        ", ".join("%s %d" % (s, statuses.get(s, 0)) for s in CORE_ENUMS["status"]),
        len(ids["L"]), tail))
    print("errors %d, warnings %d, pending %d%s" % (
        rep.counts["ERROR"], rep.counts["WARNING"], rep.counts["PENDING"],
        " (required: %s)" % ", ".join(sorted(require)) if require else ""))
    print("RESULT: %s" % ("FAIL" if rep.counts["ERROR"] else "OK"))
    return 1 if rep.counts["ERROR"] else 0
