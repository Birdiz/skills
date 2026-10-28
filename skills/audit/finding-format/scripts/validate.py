#!/usr/bin/env python3
"""Check an audit workspace's findings files and remediation plan against
finding-format (schema.md, SKILL.md) and remediation-plan. Read-only.

Usage: python3 -I validate.py <workspace> [--require verification] [--require plan]

Prints one line per problem, then a summary:
  ERROR    the form breaks the schema, or a rule a parser or a later step relies on
  WARNING  legacy form or a citation that does not resolve; nothing downstream breaks
  PENDING  a step still has to run (named); an error under the matching --require
Exit status: 0 no error, 1 errors, 2 the workspace cannot be read.
Python 3.8 or later, standard library only.
"""
import os
import re
import sys

VERSION = "finding-format@0.25.0"

AXES = {
    "code-quality": "QUA", "architecture": "ARC", "app-security": "SEC",
    "infra-security": "INF", "privacy": "PRI", "accessibility": "A11Y",
    "seo": "SEO", "performance": "PERF",
}
SEVERITIES = ["info", "low", "medium", "high", "critical"]
EFFORTS = ["S", "M", "L"]
FINDING_ENUMS = {
    "status": ["unverified", "confirmed", "refuted"],
    "severity": SEVERITIES,
    "confidence": ["high", "medium", "low"],
    "evidence_regime": ["static", "dynamic", "declarative"],
    "effort": EFFORTS,
    "resolution": ["open", "accepted", "fixed"],
}
FINDING_KEYS = ["id", "axis", "status", "severity", "confidence", "evidence_regime",
                "effort", "resolution", "sensitive", "promptable", "locations",
                "commit", "references"]
FINDING_OPTIONAL = ["verification"]
FINDING_LEGACY = ["impact"]
PROSE = ["Evidence", "Technical explanation", "Plain-language explanation", "Remediation"]
SECTIONS = ["Coverage", "Findings", "Leads", "Leads for other axes",
            "Questions for the auditor", "Created on target"]
REQUIRED_SECTIONS = SECTIONS[:3]
AREA_STATUSES = ["evaluated", "partial", "not-evaluable", "not-requested"]
VERIFIERS = ["sub-agent", "new session"]

FIX_ENUMS = {
    "grouping": ["single", "one-change", "same-files"],
    "status": ["open", "done", "dropped"],
    "severity": SEVERITIES,
    "effort": EFFORTS,
    "executor": ["code", "operations", "owner"],
}
FIX_KEYS = ["id", "findings", "grouping", "status", "severity", "effort", "executor",
            "promptable", "sensitive", "waits_for", "locations"]
FIX_PROSE = ["Grouping", "Change", "Check"]
PLAN_HEADER = ["commit", "skill", "tools", "findings", "generated"]
PLAN_SECTIONS = ["Order", "Fixes", "Discrepancies"]

CODES = "|".join(sorted(AXES.values(), key=len, reverse=True))
F_ID = re.compile(r"\bF-(%s)-(\d+)\b" % CODES)
L_ID = re.compile(r"\bL-(%s)-(\d+)\b" % CODES)
Q_ID = re.compile(r"\bQ-(%s)-(\d+)\b" % CODES)
R_ID = re.compile(r"\bR-(\d+)\b")
DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
RECHECK = re.compile(r"Re-checked \d{4}-\d{2}-\d{2}, answer of (\d{4}-\d{2}-\d{2}): no change\b")
FIXCHECK = re.compile(r"Fix checked (\d{4}-\d{2}-\d{2}) at ([0-9a-f]{7,40}): (fixed by|in part|not fixed)\b")
WORKSPACE = re.compile(r"^(\./)?(findings/(%s)\.md|tool-output/|client-docs/"
                       r"|0[0-2]-(engagement|codebase-map|remediation-plan)\.md"
                       r"|tickets/(index|R-\d{3})(\.sent)?\.md"
                       r"|reports/(peer-report|summary|remediation-prompts)\.md)" % "|".join(AXES))
FENCE = re.compile(r"^(`{3,}|~{3,})")


class Report:
    def __init__(self, root):
        self.root = root
        self.lines = []
        self.counts = {"ERROR": 0, "WARNING": 0, "PENDING": 0}

    def add(self, kind, path, line, msg, step=None):
        where = os.path.relpath(path, self.root) + (":%d" % line if line else "")
        label = kind if step is None else "%s %s" % (kind, step)
        self.lines.append((kind, step, "%-8s %s  %s" % (label, where, msg)))
        self.counts[kind] += 1

    def error(self, path, line, msg):
        self.add("ERROR", path, line, msg)

    def warn(self, path, line, msg):
        self.add("WARNING", path, line, msg)

    def pending(self, step, path, line, msg):
        self.add("PENDING", path, line, msg, step)


# --- YAML: the flat subset the schema uses ---------------------------------

def scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text == "true":
        return True
    if text == "false":
        return False
    return text


def split_flow(text):
    parts, depth, quote, cur = [], 0, None, ""
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch in "[{":
            depth += 1
            cur += ch
        elif ch in "]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts]


def strip_comment(text):
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def value(text):
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return [scalar(p) for p in split_flow(text[1:-1])]
    if text.startswith("{") and text.endswith("}"):
        out = {}
        for part in split_flow(text[1:-1]):
            if ":" not in part:
                raise ValueError("flow mapping entry without a colon: %s" % part)
            k, v = part.split(":", 1)
            out[k.strip()] = scalar(v)
        return out
    return scalar(text)


def parse_yaml(lines):
    """Returns (dict, [(line offset, message)])."""
    data, problems, key = {}, [], None
    for i, raw in enumerate(lines):
        line = strip_comment(raw)
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(?:\s+(.*))?$", line)
        if m:
            key = m.group(1)
            if key in data:
                problems.append((i, "key `%s` given twice" % key))
            try:
                data[key] = value(m.group(2)) if m.group(2) else []
            except ValueError as e:
                problems.append((i, str(e)))
            continue
        m = re.match(r"^\s+-\s+(.*)$", line)
        if m and key is not None and isinstance(data.get(key), list):
            data[key].append(scalar(m.group(1)))
            continue
        problems.append((i, "unreadable YAML line: %s" % raw.strip()))
    return data, problems


# --- Markdown structure ----------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n")


def outside_fences(lines):
    """Yields (index, line, None, None) for each line outside fenced blocks,
    and (index of the opening fence, None, info string, body lines) for each block."""
    fence, start, info, body = None, 0, "", []
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if fence is None and m:
            fence, start, info, body = m.group(1), i, line[len(m.group(1)):].strip(), []
            continue
        if fence is not None:
            if line.strip().startswith(fence[0] * len(fence)) and line.strip().strip(fence[0]) == "":
                yield start, None, info, body
                fence = None
            else:
                body.append(line)
            continue
        yield i, line, None, None


def blocks(lines, level):
    """Splits lines by headings of the given level, fences ignored.
    Returns [(heading text or None, start index, [(index, line or None, info, body)])]."""
    mark = "#" * level + " "
    out = [(None, 0, [])]
    for item in outside_fences(lines):
        i, line = item[0], item[1]
        if line is not None and line.startswith(mark):
            out.append((line[len(mark):].strip(), i, []))
        elif line is not None and level == 3 and line.startswith("## "):
            out.append((None, i, []))
        else:
            out[-1][2].append(item)
    return out


def paragraphs(items):
    """Groups prose lines into paragraphs: [(index of first line, text)]."""
    out, cur, start = [], [], None
    for i, line, _, _ in items:
        if line is None or not line.strip():
            if cur:
                out.append((start, " ".join(cur)))
            cur, start = [], None
            continue
        if start is None:
            start = i
        cur.append(line.strip())
    if cur:
        out.append((start, " ".join(cur)))
    return out


def bullets(items):
    """Top-level list items: [(index, text)], continuation lines joined."""
    out = []
    for i, line, _, _ in items:
        if line is None:
            continue
        if re.match(r"^(-|\*|\d+\.)\s", line):
            out.append([i, line.strip()])
        elif out and line.strip() and (line.startswith(" ") or line.startswith("\t")):
            out[-1][1] += " " + line.strip()
        elif not line.strip():
            continue
        elif out and not line.startswith("#"):
            out.append([None, None])
    return [(i, t) for i, t in out if t is not None]


# --- Findings files --------------------------------------------------------

class Finding:
    def __init__(self, path, line, data, labels, text):
        self.path, self.line, self.data, self.labels, self.text = path, line, data, labels, text
        self.dates = []


def label_of(paragraph):
    m = re.match(r"^\*\*([^*]+?)\.\*\*", paragraph)
    return m.group(1) if m else None


def check_finding(rep, path, axis, title, start, items, engagement_commit):
    code = AXES[axis]
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
    for off, msg in problems:
        rep.error(path, yi + 2 + off, "%s: %s" % (fid, msg))
    for k in FINDING_KEYS:
        if k not in data:
            rep.error(path, yi + 1, "%s: key `%s` missing" % (fid, k))
    for k in data:
        if k not in FINDING_KEYS + FINDING_OPTIONAL + FINDING_LEGACY:
            rep.warn(path, yi + 1, "%s: key `%s` is not in the schema" % (fid, k))
    for k, allowed in FINDING_ENUMS.items():
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
    if "references" in data and not isinstance(data["references"], list):
        rep.error(path, yi + 1, "%s: references must be a list (empty allowed)" % fid)
    commit = str(data.get("commit", ""))
    if commit and not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        rep.error(path, yi + 1, "%s: commit `%s` is not a hexadecimal SHA" % (fid, commit))
    elif commit and engagement_commit and not (engagement_commit.startswith(commit) or commit.startswith(engagement_commit)):
        rep.warn(path, yi + 1, "%s: commit %s differs from the engagement's %s" % (fid, commit, engagement_commit))

    ver = data.get("verification")
    if ver is not None:
        if not isinstance(ver, dict) or set(ver) != {"by", "on"}:
            rep.error(path, yi + 1, "%s: verification must be {by: <who>, on: <YYYY-MM-DD>}" % fid)
            ver = None
        else:
            if ver["by"] not in VERIFIERS:
                rep.error(path, yi + 1, "%s: verification by `%s` not in %s" % (fid, ver["by"], " | ".join(VERIFIERS)))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(ver["on"])):
                rep.error(path, yi + 1, "%s: verification on `%s` is not a date" % (fid, ver["on"]))

    rest = [it for it in items if it[0] > yi]
    paras = paragraphs(rest)
    labels = [(i, label_of(p), p) for i, p in paras if label_of(p)]
    names = [l for _, l, _ in labels]
    for name in PROSE:
        n = names.count(name)
        if n == 0:
            rep.error(path, start + 1, "%s: **%s.** missing" % (fid, name))
        elif n > 1:
            rep.error(path, start + 1, "%s: **%s.** given %d times" % (fid, name, n))
    order = [n for n in names if n in PROSE + ["Verification", "Auditor answer"]]
    expected = [n for n in PROSE + ["Verification"] if n in order]
    seen = [n for n in order if n != "Auditor answer"]
    dedup = [n for k, n in enumerate(seen) if n not in seen[:k]]
    if dedup != expected:
        rep.error(path, start + 1, "%s: prose sections out of order (%s)" % (fid, ", ".join(dedup)))
    if "Auditor answer" in names and "Verification" in names and names.index("Auditor answer") < names.index("Verification"):
        rep.error(path, start + 1, "%s: **Auditor answer.** comes before **Verification.**" % fid)

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
        rep.pending("verify-findings", path, start + 1, "%s: not verified yet" % fid)
    answers = [(i, p) for i, l, p in labels if l == "Auditor answer"]
    if data.get("resolution") == "accepted" and not answers:
        rep.error(path, start + 1, "%s: resolution accepted without an **Auditor answer.**" % fid)
    dates = [DATE.search(p).group(1) for _, p in answers if DATE.search(p)]
    if len(dates) < len(answers):
        rep.warn(path, start + 1, "%s: an **Auditor answer.** carries no date" % fid)
    rechecked = set(RECHECK.findall(" ".join(p for _, p in paras)))
    if ver is not None and dates:
        late = [d for d in dates if d > str(ver["on"]) and d not in rechecked]
        if late:
            rep.pending("verify-findings", path, start + 1,
                        "%s: auditor answer %s after verification %s" % (fid, max(late), ver["on"]))
    text = " ".join(p for _, p in paras)
    checks = sorted(FIXCHECK.findall(text))
    if checks:
        fixed = checks[-1][2] == "fixed by"
        if fixed != (data.get("resolution") == "fixed"):
            rep.error(path, yi + 1, "%s: resolution %s, its last fix check (%s at %s) says %s"
                      % (fid, data.get("resolution"), checks[-1][0], checks[-1][1], checks[-1][2]))
        if ver is not None and checks[-1][0] > str(ver["on"]):
            rep.error(path, yi + 1, "%s: fix checked %s, verification `on` still %s" % (fid, checks[-1][0], ver["on"]))
    elif data.get("resolution") == "fixed":
        rep.error(path, start + 1, "%s: resolution fixed without a `Fix checked <date> at <commit>: fixed by …` line" % fid)
    if data.get("evidence_regime") == "declarative" and not Q_ID.search(text + " " + " ".join(map(str, data.get("locations") or []))):
        rep.warn(path, start + 1, "%s: declarative finding cites no question ID" % fid)
    finding = Finding(path, start + 1, data, names, text)
    finding.dates = dates + [c[0] for c in checks] + ([str(ver["on"])] if ver is not None else [])
    return finding


def check_leads(rep, path, axis, start, items, ids, refs):
    code = AXES[axis]
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
        statuses = list(re.finditer(r"(promoted to F-|closed:|open:)", text))
        if not statuses:
            rep.error(path, i + 1, "%s: no status (`promoted to F-…`, `closed:`, `open:`)" % lid)
            continue
        last = text[statuses[-1].start():]
        for m2 in re.finditer(r"(?:promoted to|settled by|remains of)\s+(F-[A-Z0-9]+-\d+)", text):
            refs.append((path, i + 1, lid, m2.group(1), "error"))
        if last.startswith("open:") and "moved from" in last[:40]:
            rep.pending("lead-pass", path, i + 1, "%s: moved into %s, waits for a lead pass" % (lid, axis))
        elif last.startswith("open:") and "from verify-findings" in last[:40]:
            rep.pending("lead-pass", path, i + 1, "%s: opened by verify-findings, waits for a lead pass" % lid)
        if last.startswith("open:") and "axis not requested" in last:
            ids["not_requested"].setdefault(axis, []).append(lid)


def check_other_axes(rep, path, items, refs):
    for i, text in bullets(items):
        m = re.search(r"moved to (L-[A-Z0-9]+-\d+)", text)
        if m:
            refs.append((path, i + 1, "moved lead", m.group(1), "error"))
            continue
        m = re.match(r"^[-*]\s+\*\*([a-z0-9-]+)\s*:", text)
        if not m:
            rep.error(path, i + 1, "lead for another axis is not `- **<axis>: <title>.**`: %s" % text[:60])
            continue
        if m.group(1) not in AXES:
            rep.error(path, i + 1, "lead for unknown axis `%s`" % m.group(1))
        rep.pending("verify-findings", path, i + 1, "lead for %s not moved yet" % m.group(1))


def check_questions(rep, path, axis, items, ids, last_pass):
    code = AXES[axis]
    for i, text in bullets(items):
        m = re.match(r"^[-*]\s+(?:\*\*)?(Q-[A-Z0-9]+-\d+)", text)
        if not m:
            rep.warn(path, i + 1, "question without ID (older skills): the next step writing this file numbers it")
            ids["Q_unnumbered"] += 1
            qid = "question"
        else:
            qid = m.group(1)
            if not re.fullmatch(r"Q-%s-\d{2,}" % code, qid):
                rep.error(path, i + 1, "%s: ID does not follow Q-%s-<NN> for this file" % (qid, code))
            if qid in ids["Q"]:
                rep.error(path, i + 1, "%s: ID used twice (also %s)" % (qid, ids["Q"][qid]))
            ids["Q"][qid] = "%s:%d" % (os.path.relpath(path, rep.root), i + 1)
        for m2 in re.finditer(r"\*\*(Answer|Asked)\b[^*]*\*\*", text):
            mark = m2.group(0)
            if m2.group(1) == "Answer" and not re.match(r"\*\*Answer \(\d{4}-\d{2}-\d{2}, [^)]+\)\s*:\*\*", mark):
                rep.error(path, i + 1, "%s: answer not `**Answer (YYYY-MM-DD, who):**`: %s" % (qid, mark))
            elif m2.group(1) == "Answer" and last_pass and mark[10:20] > last_pass:
                rep.pending("lead-pass", path, i + 1, "%s: answered %s, after the axis's last pass (%s): waits for a lead pass" % (qid, mark[10:20], last_pass))
            if m2.group(1) == "Asked" and not re.match(r"\*\*Asked \(\d{4}-\d{2}-\d{2}\), not answered\.\*\*", mark):
                rep.error(path, i + 1, "%s: not `**Asked (YYYY-MM-DD), not answered.**`: %s" % (qid, mark))


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


def last_pass(sections, axis):
    """Date of the axis's last pass: the newest date in a coverage paragraph
    naming the axis's own skill and version (its run, or a lead pass); None
    when no paragraph names it (older skills), so nothing is checked."""
    for name, _, items in sections:
        if name != "Coverage":
            continue
        paras, cur = [], []
        for _, line, _, _ in items:
            if line is None or not line.strip() or re.match(r"\s*[-*|]", line):
                paras.append(" ".join(cur))
                cur = [line] if line and re.match(r"\s*[-*]", line) else []
            else:
                cur.append(line)
        paras.append(" ".join(cur))
        dates = [d for p in paras if re.search(r"\b%s@\d" % re.escape(axis), p)
                 for d in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", p)]
        return max(dates) if dates else None
    return None


def check_findings_file(rep, path, axis, engagement_commit, ids, refs, findings):
    lines = read(path)
    sections = blocks(lines, 2)
    names = [h for h, _, _ in sections[1:]]
    for name in names:
        if name not in SECTIONS:
            rep.warn(path, None, "section `## %s` is not in finding-format" % name)
    for name in REQUIRED_SECTIONS:
        if name not in names:
            rep.error(path, None, "section `## %s` missing" % name)
    known = [n for n in names if n in SECTIONS]
    if known != sorted(known, key=SECTIONS.index) or len(set(known)) != len(known):
        rep.error(path, None, "sections out of order or repeated: %s" % ", ".join(known))
    for name, start, items in sections[1:]:
        if name == "Coverage":
            check_coverage(rep, path, start, items)
        elif name == "Findings":
            end = next((st for _, st, _ in sections if st > start), len(lines))
            for title, s, sub in blocks(lines, 3)[1:]:
                if title is None or not start < s < end:
                    continue
                f = check_finding(rep, path, axis, title, s, sub, engagement_commit)
                if f is None:
                    continue
                fid = f.data.get("id") or title.split()[0]
                if fid in ids["F"]:
                    rep.error(path, s + 1, "%s: ID used twice (also %s)" % (fid, ids["F"][fid]))
                ids["F"][fid] = "%s:%d" % (os.path.relpath(path, rep.root), s + 1)
                findings[fid] = f
        elif name == "Leads":
            check_leads(rep, path, axis, start, items, ids, refs)
        elif name == "Leads for other axes":
            check_other_axes(rep, path, items, refs)
        elif name == "Questions for the auditor":
            check_questions(rep, path, axis, items, ids, last_pass(sections[1:], axis))
    text = "\n".join(lines)
    for regex in (F_ID, L_ID, Q_ID):
        for m in regex.finditer(text):
            refs.append((path, text.count("\n", 0, m.start()) + 1, None, m.group(0), "warning"))


# --- Remediation plan ------------------------------------------------------

def check_plan(rep, path, findings, ids, engagement_commit):
    lines = read(path)
    header = {}
    for line in lines[:15]:
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if m:
            header[m.group(1)] = m.group(2).strip()
    for k in PLAN_HEADER:
        if k not in header:
            rep.error(path, None, "plan header `%s:` missing" % k)
    generated = header.get("generated", "")
    if generated and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", generated):
        rep.error(path, None, "plan `generated: %s` is not a date" % generated)
    pc = header.get("commit", "")
    if pc and engagement_commit and not (engagement_commit.startswith(pc) or pc.startswith(engagement_commit)):
        rep.warn(path, None, "plan commit %s differs from the engagement's %s" % (pc, engagement_commit))
    sections = blocks(lines, 2)
    names = [h for h, _, _ in sections[1:]]
    for name in PLAN_SECTIONS:
        if name not in names:
            rep.error(path, None, "section `## %s` missing" % name)

    fixes, older = {}, []
    for title, s, sub in blocks(lines, 3)[1:]:
        if title is None:
            continue
        m = re.match(r"^(R-\d+)\s+(\S.*)$", title)
        if not m:
            continue
        rid, rtitle = m.group(1), m.group(2).strip()
        if not re.fullmatch(r"R-\d{3}", rid):
            rep.error(path, s + 1, "%s: ID does not follow R-<NNN>" % rid)
        if rid in fixes:
            rep.error(path, s + 1, "%s: ID used twice" % rid)
        first = next(((line, info, body) for _, line, info, body in sub if line is None or line.strip()), None)
        if first is None or first[0] is not None or first[1] != "yaml":
            rep.error(path, s + 1, "%s: no YAML block right after the heading" % rid)
            continue
        yi = next(i for i, line, info, _ in sub if line is None)
        data, problems = parse_yaml(first[2])
        for off, msg in problems:
            rep.error(path, yi + 2 + off, "%s: %s" % (rid, msg))
        for k in FIX_KEYS:
            if k not in data:
                rep.error(path, yi + 1, "%s: key `%s` missing" % (rid, k))
        for k, allowed in FIX_ENUMS.items():
            if k in data and data[k] not in allowed:
                rep.error(path, yi + 1, "%s: %s `%s` not in %s" % (rid, k, data[k], " | ".join(allowed)))
        for k in ("promptable", "sensitive"):
            if k in data and not isinstance(data[k], bool):
                rep.error(path, yi + 1, "%s: %s must be true or false" % (rid, k))
        for k in ("findings", "waits_for", "locations"):
            if k in data and not isinstance(data[k], list):
                rep.error(path, yi + 1, "%s: %s must be a list" % (rid, k))
                data[k] = []
        if data.get("id") not in (None, rid):
            rep.error(path, yi + 1, "%s: id `%s` differs from the heading" % (rid, data["id"]))
        labels = [label_of(p) for _, p in paragraphs([it for it in sub if it[0] > yi])]
        if "Grouping" not in labels and "Why together" in labels:
            older.append(rid)
            labels.append("Grouping")
        for name in FIX_PROSE:
            if name not in labels:
                rep.error(path, s + 1, "%s: **%s.** missing" % (rid, name))
        data["_title"], data["_line"] = rtitle, s + 1
        fixes[rid] = data
    if older:
        rep.warn(path, None, "%d fixes use **Why together.**, the older label of **Grouping.** (%s to %s)"
                 % (len(older), older[0], older[-1]))

    where = {}
    for rid, d in fixes.items():
        fs = d.get("findings") or []
        if d.get("status") == "open" and not fs:
            rep.error(path, d["_line"], "%s: open fix without findings" % rid)
        if d.get("status") == "open" and fs and (len(fs) == 1) != (d.get("grouping") == "single"):
            rep.error(path, d["_line"], "%s: grouping %s with %d findings" % (rid, d.get("grouping"), len(fs)))
        for f in fs:
            where.setdefault(f, []).append(rid)
            if f not in findings:
                rep.error(path, d["_line"], "%s: finding %s does not exist" % (rid, f))
            elif d.get("status") == "open":
                fd = findings[f].data
                if (fd.get("status"), fd.get("resolution")) != ("confirmed", "open"):
                    rep.pending("remediation-plan", path, d["_line"],
                                "%s: %s is %s/%s, no longer confirmed and open" % (rid, f, fd.get("status"), fd.get("resolution")))
        known = [findings[f].data for f in fs if f in findings]
        if d.get("status") == "open" and d.get("grouping") == "same-files" and \
                len({x.get("sensitive") is True for x in known}) > 1:
            rep.error(path, d["_line"], "%s: same-files group mixes sensitive and non-sensitive findings" % rid)
        for loc in (d.get("locations") or []) if d.get("status") == "open" else []:
            loc = str(loc)
            head = (loc.split() or [""])[0]
            inside = os.path.isabs(head) and os.path.abspath(head).startswith(os.path.abspath(rep.root) + os.sep)
            if inside or WORKSPACE.search(loc) or L_ID.search(loc) or Q_ID.search(loc):
                rep.error(path, d["_line"], "%s: location `%s` points into the workspace, not where the change lands" % (rid, loc))
        if d.get("status") == "open" and known:
            sev = max((x.get("severity") for x in known if x.get("severity") in SEVERITIES),
                      key=SEVERITIES.index, default=None)
            derived = {"severity": sev,
                       "promptable": all(x.get("promptable") is True for x in known),
                       "sensitive": any(x.get("sensitive") is True for x in known)}
            for k, v in derived.items():
                if k in d and v is not None and d[k] != v:
                    rep.error(path, d["_line"], "%s: %s %s, its findings give %s" % (rid, k, d[k], v))
        if d.get("status") == "done":
            for f in fs:
                if f in findings and findings[f].data.get("resolution") != "fixed":
                    rep.error(path, d["_line"], "%s: done, but %s is not fixed" % (rid, f))
        for w in d.get("waits_for") or []:
            w = str(w)
            if re.fullmatch(r"R-\d+", w) and w not in fixes:
                rep.error(path, d["_line"], "%s: waits for unknown fix %s" % (rid, w))
            elif re.fullmatch(r"R-\d+", w) and d.get("status") == "open" and fixes[w].get("status") != "open":
                rep.pending("remediation-plan", path, d["_line"], "%s: waits for %s, which is %s" % (rid, w, fixes[w].get("status")))
            if re.fullmatch(r"Q-[A-Z0-9]+-\d+", w) and w not in ids["Q"]:
                rep.error(path, d["_line"], "%s: waits for unknown question %s" % (rid, w))
    for f, rs in where.items():
        if len(rs) > 1:
            rep.error(path, None, "%s is in several fixes: %s" % (f, ", ".join(rs)))
    for fid, f in sorted(findings.items()):
        if (f.data.get("status"), f.data.get("resolution")) == ("confirmed", "open"):
            if not [r for r in where.get(fid, []) if fixes[r].get("status") == "open"]:
                rep.pending("remediation-plan", f.path, f.line, "%s: confirmed and open, in no open fix" % fid)
        if generated:
            if f.dates and max(f.dates) > generated:
                rep.pending("remediation-plan", f.path, f.line,
                            "%s: verified or answered %s, after the plan (generated %s)" % (fid, max(f.dates), generated))

    check_order(rep, path, lines, fixes)
    return fixes


def check_order(rep, path, lines, fixes):
    rows = []
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) >= 8 and re.fullmatch(r"R-\d+", cells[1]):
            rows.append((i + 1, cells))
    ids = [c[1] for _, c in rows]
    for rid, d in fixes.items():
        if d.get("status") == "open" and ids.count(rid) != 1:
            rep.error(path, d["_line"], "%s: open fix listed %d times in `## Order`" % (rid, ids.count(rid)))
    for rid in set(ids) - set(fixes):
        rep.error(path, None, "`## Order` lists %s, which has no section" % rid)
    for rid in sorted(set(ids) & set(fixes)):
        if fixes[rid].get("status") != "open":
            rep.error(path, fixes[rid]["_line"], "%s: %s fix listed in `## Order`" % (rid, fixes[rid].get("status")))
    pos = {rid: k for k, rid in enumerate(ids)}

    def tier(d):
        ws = [str(w) for w in d.get("waits_for") or []]
        return 2 if any(not re.fullmatch(r"R-\d+", w) for w in ws) else (1 if ws else 0)

    prev = None
    for n, cells in rows:
        rid = cells[1]
        d = fixes.get(rid)
        if d is None:
            continue
        for k, col in (("_title", 2), ("severity", 3), ("effort", 4), ("executor", 5)):
            if str(d.get(k)) != cells[col]:
                rep.error(path, n, "%s: `## Order` %s `%s`, YAML `%s`" % (rid, k.strip("_"), cells[col], d.get(k)))
        waits = [] if cells[6] in ("—", "-", "") else [w.strip() for w in cells[6].split(";") if w.strip()]
        yw = [str(w) for w in d.get("waits_for") or []]
        if sorted(waits) != sorted(yw):
            rep.error(path, n, "%s: `## Order` waits for %s, YAML %s" % (rid, waits or "nothing", yw or "nothing"))
        quick = (d.get("status") == "open" and d.get("severity") in SEVERITIES
                 and SEVERITIES.index(d.get("severity")) >= 2 and d.get("effort") == "S" and not yw)
        if cells[7] not in ("yes", "no"):
            rep.error(path, n, "%s: quick win `%s` is not yes or no" % (rid, cells[7]))
        elif (cells[7] == "yes") != quick:
            rep.error(path, n, "%s: quick win `%s`, derived %s" % (rid, cells[7], "yes" if quick else "no"))
        for w in yw:
            if re.fullmatch(r"R-\d+", w) and pos.get(w, -1) > pos[rid]:
                rep.error(path, n, "%s comes before %s, which it waits for" % (rid, w))
        key = (tier(d), -SEVERITIES.index(d["severity"]) if d.get("severity") in SEVERITIES else 0,
               EFFORTS.index(d["effort"]) if d.get("effort") in EFFORTS else 0)
        if prev is not None and key[0] < prev[1][0]:
            rep.error(path, n, "%s (tier %d) after %s (tier %d)" % (rid, key[0], prev[0], prev[1][0]))
        elif prev is not None and key[0] == prev[1][0] and key[0] == 0 and key < prev[1]:
            rep.warn(path, n, "%s after %s: not by severity, then effort" % (rid, prev[0]))
        prev = (rid, key)


# --- Workspace -------------------------------------------------------------

def engagement_commit(root, rep):
    path = os.path.join(root, "00-engagement.md")
    if not os.path.exists(path):
        rep.warn(path, None, "engagement file missing: commits not compared")
        return None
    for line in read(path):
        m = re.match(r"^commit:\s*([0-9a-f]{7,40})\b", line.strip())
        if m:
            return m.group(1)
    rep.warn(path, None, "no `commit:` in the engagement file: commits not compared")
    return None


def main(argv):
    args = argv[1:]
    require = set()
    root = None
    while args:
        a = args.pop(0)
        if a == "--require" and args:
            require.add(args.pop(0))
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        elif a == "--version":
            print(VERSION)
            return 0
        elif root is None and not a.startswith("-"):
            root = a
        else:
            print("unknown argument: %s" % a, file=sys.stderr)
            return 2
    if root is None or not require <= {"verification", "plan"}:
        print(__doc__, file=sys.stderr)
        return 2
    fdir = os.path.join(root, "findings")
    if not os.path.isdir(fdir):
        print("no findings/ directory in %s" % root, file=sys.stderr)
        return 2

    rep = Report(root)
    commit = engagement_commit(root, rep)
    ids = {"F": {}, "L": {}, "Q": {}, "Q_unnumbered": 0, "not_requested": {}}
    refs, findings = [], {}
    for name in sorted(os.listdir(fdir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(fdir, name)
        axis = name[:-3]
        if axis not in AXES:
            rep.error(path, None, "`%s` is not an axis of finding-format" % axis)
            continue
        check_findings_file(rep, path, axis, commit, ids, refs, findings)

    known = set(ids["F"]) | set(ids["L"]) | set(ids["Q"])
    seen = set()
    for path, line, owner, target, level in refs:
        if target in known or (path, target, level) in seen:
            continue
        seen.add((path, target, level))
        if level == "error":
            rep.error(path, line, "%s points to %s, which does not exist" % (owner, target))
        else:
            rep.warn(path, line, "%s is cited but defined nowhere in findings/" % target)

    plan_path = os.path.join(root, "02-remediation-plan.md")
    fixes = {}
    if os.path.exists(plan_path):
        fixes = check_plan(rep, plan_path, findings, ids, commit)
    elif any((f.data.get("status"), f.data.get("resolution")) == ("confirmed", "open") for f in findings.values()):
        rep.pending("remediation-plan", plan_path, None, "no plan yet")

    for kind, step, text in rep.lines:
        if kind == "PENDING" and ((step == "verify-findings" and "verification" in require)
                                  or (step == "remediation-plan" and "plan" in require)):
            text = text.replace("PENDING", "ERROR  ", 1)
            rep.counts["PENDING"] -= 1
            rep.counts["ERROR"] += 1
        print(text)

    statuses = {}
    for f in findings.values():
        statuses[f.data.get("status")] = statuses.get(f.data.get("status"), 0) + 1
    print("%s: %d findings (%s), %d leads, %d questions, %d fixes (%d open)" % (
        VERSION, len(findings),
        ", ".join("%s %d" % (s, statuses.get(s, 0)) for s in FINDING_ENUMS["status"]),
        len(ids["L"]), len(ids["Q"]) + ids["Q_unnumbered"], len(fixes),
        sum(1 for d in fixes.values() if d.get("status") == "open")))
    print("errors %d, warnings %d, pending %d%s" % (
        rep.counts["ERROR"], rep.counts["WARNING"], rep.counts["PENDING"],
        " (required: %s)" % ", ".join(sorted(require)) if require else ""))
    print("RESULT: %s" % ("FAIL" if rep.counts["ERROR"] else "OK"))
    return 1 if rep.counts["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
