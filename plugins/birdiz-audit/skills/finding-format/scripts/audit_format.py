"""The audit extension of the finding core: what finding-format and
remediation-plan add to the core schema, and the audit workspace layout.

- Axes and their codes; the extra keys `evidence_regime`, `effort`,
  `resolution`, `commit`, `references`; the prose sections; the `##`
  sections and their order.
- Leads moved between axes, questions for the auditor and their marks,
  auditor answers and fix checks on findings.
- The engagement's `execution`, and the remediation plan against its findings.
- Where pointers open: the working copy, the dependency installs the
  codebase map names, `tool-output/`, `client-docs/`, `repo-<short sha>/`.
"""
import glob
import os
import re

from finding_core import pointers
from finding_core.markdown import blocks, bullets, label_of, paragraphs, parse_yaml, read, strip_comment
from finding_core.validator import CORE_KEYS, DATE, SEVERITIES, Extension, id_pattern

VERSION = "finding-format@0.27.0"

AXES = {
    "code-quality": "QUA", "architecture": "ARC", "app-security": "SEC",
    "infra-security": "INF", "privacy": "PRI", "accessibility": "A11Y",
    "seo": "SEO", "performance": "PERF",
}
EFFORTS = ["S", "M", "L"]
EXECUTIONS = ["none", "disposable-copy", "local-target"]

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

L_ID = id_pattern("L", AXES.values())
Q_ID = id_pattern("Q", AXES.values())
RECHECK = re.compile(r"Re-checked \d{4}-\d{2}-\d{2}, answer of (\d{4}-\d{2}-\d{2}): no change\b")
FIXCHECK = re.compile(r"Fix checked (\d{4}-\d{2}-\d{2}) at ([0-9a-f]{7,40}): (fixed by|in part|not fixed)\b")
WORKSPACE = re.compile(r"^(\./)?(findings/(%s)\.md|tool-output/|client-docs/"
                       r"|0[0-2]-(engagement|codebase-map|remediation-plan)\.md"
                       r"|tickets/(index|R-\d{3})(\.sent)?\.md"
                       r"|reports/(peer-report|summary|remediation-prompts)\.md)" % "|".join(AXES))

ENGAGEMENT = "00-engagement.md"
CODEBASE_MAP = "01-codebase-map.md"
PLAN = "02-remediation-plan.md"


def _schema_keys():
    keys = CORE_KEYS[:5] + ["evidence_regime", "effort", "resolution"] + CORE_KEYS[5:] + ["commit", "references"]
    assert set(CORE_KEYS) <= set(keys)
    return keys


class AuditExtension(Extension):
    name = VERSION
    schema = "finding-format"
    axes = AXES
    keys = _schema_keys()
    legacy = ["impact"]
    enums = {
        "evidence_regime": ["static", "dynamic", "declarative"],
        "effort": EFFORTS,
        "resolution": ["open", "accepted", "fixed"],
    }
    prose = ["Evidence", "Technical explanation", "Plain-language explanation", "Remediation"]
    trailing = ["Auditor answer"]
    sections = ["Coverage", "Findings", "Leads", "Leads for other axes",
                "Questions for the auditor", "Created on target"]
    required_sections = sections[:3]
    id_prefixes = ["F", "L", "Q"]
    lead_links = ["promoted to", "settled by", "remains of"]
    requirable = {"verification": "verify-findings", "plan": "remediation-plan"}

    def __init__(self, rep, root):
        super().__init__(rep, root)
        self.unnumbered = 0
        self.fixes = {}
        self.commit = engagement_commit(root, rep)
        check_engagement(root, rep)

    # --- findings -----------------------------------------------------------

    def check_keys(self, f):
        rep, path, yi, fid, data = self.rep, f.path, f.yi, f.fid, f.data
        if "references" in data and not isinstance(data["references"], list):
            rep.error(path, yi + 1, "%s: references must be a list (empty allowed)" % fid)
        commit = str(data.get("commit", ""))
        if commit and not re.fullmatch(r"[0-9a-f]{7,40}", commit):
            rep.error(path, yi + 1, "%s: commit `%s` is not a hexadecimal SHA" % (fid, commit))
        elif commit and self.commit and not (self.commit.startswith(commit) or commit.startswith(self.commit)):
            rep.warn(path, yi + 1, "%s: commit %s differs from the engagement's %s" % (fid, commit, self.commit))

    def check_prose(self, f):
        rep, path, start, yi, fid, data, ver = self.rep, f.path, f.start, f.yi, f.fid, f.data, f.ver
        answers = [(i, p) for i, l, p in f.labels if l == "Auditor answer"]
        if data.get("resolution") == "accepted" and not answers:
            rep.error(path, start + 1, "%s: resolution accepted without an **Auditor answer.**" % fid)
        dates = [DATE.search(p).group(1) for _, p in answers if DATE.search(p)]
        if len(dates) < len(answers):
            rep.warn(path, start + 1, "%s: an **Auditor answer.** carries no date" % fid)
        rechecked = set(RECHECK.findall(f.text))
        if ver is not None and dates:
            late = [d for d in dates if d > str(ver["on"]) and d not in rechecked]
            if late:
                rep.pending("verify-findings", path, start + 1,
                            "%s: auditor answer %s after verification %s" % (fid, max(late), ver["on"]))
        checks = sorted(FIXCHECK.findall(f.text))
        if checks:
            fixed = checks[-1][2] == "fixed by"
            if fixed != (data.get("resolution") == "fixed"):
                rep.error(path, yi + 1, "%s: resolution %s, its last fix check (%s at %s) says %s"
                          % (fid, data.get("resolution"), checks[-1][0], checks[-1][1], checks[-1][2]))
            if ver is not None and checks[-1][0] > str(ver["on"]):
                rep.error(path, yi + 1, "%s: fix checked %s, verification `on` still %s" % (fid, checks[-1][0], ver["on"]))
        elif data.get("resolution") == "fixed":
            rep.error(path, start + 1, "%s: resolution fixed without a `Fix checked <date> at <commit>: fixed by …` line" % fid)
        if data.get("evidence_regime") == "declarative" and not Q_ID.search(f.text + " " + " ".join(map(str, data.get("locations") or []))):
            rep.warn(path, start + 1, "%s: declarative finding cites no question ID" % fid)
        return dates + [c[0] for c in checks]

    def check_lead(self, path, line, lid, axis, last):
        if last.startswith("open:") and "moved from" in last[:40]:
            self.rep.pending("lead-pass", path, line, "%s: moved into %s, waits for a lead pass" % (lid, axis))
        elif last.startswith("open:") and "from verify-findings" in last[:40]:
            self.rep.pending("lead-pass", path, line, "%s: opened by verify-findings, waits for a lead pass" % lid)

    def check_section(self, name, path, axis, start, items, sections, lines, ids, refs):
        if name == "Leads for other axes":
            check_other_axes(self.rep, path, items, refs)
        elif name == "Questions for the auditor":
            self.unnumbered += check_questions(self.rep, path, axis, items, ids,
                                               last_pass(sections, axis), marks_applied(lines, axis))

    def finish(self, findings, ids):
        plan_path = os.path.join(self.root, PLAN)
        if os.path.exists(plan_path):
            self.fixes = check_plan(self.rep, plan_path, findings, ids, self.commit)
        elif any((f.data.get("status"), f.data.get("resolution")) == ("confirmed", "open") for f in findings.values()):
            self.rep.pending("remediation-plan", plan_path, None, "no plan yet")
        return ", %d questions, %d fixes (%d open)" % (
            len(ids["Q"]) + self.unnumbered, len(self.fixes),
            sum(1 for d in self.fixes.values() if d.get("status") == "open"))


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


def check_questions(rep, path, axis, items, ids, last_pass, marks_applied):
    """Returns the number of questions without an ID."""
    code = AXES[axis]
    unnumbered = 0
    for i, text in bullets(items):
        m = re.match(r"^[-*]\s+(?:\*\*)?(Q-[A-Z0-9]+-\d+)", text)
        if not m:
            rep.warn(path, i + 1, "question without ID (older skills): the next step writing this file numbers it")
            unnumbered += 1
            qid = "question"
        else:
            qid = m.group(1)
            if not re.fullmatch(r"Q-%s-\d{2,}" % code, qid):
                rep.error(path, i + 1, "%s: ID does not follow Q-%s-<NN> for this file" % (qid, code))
            if qid in ids["Q"]:
                rep.error(path, i + 1, "%s: ID used twice (also %s)" % (qid, ids["Q"][qid]))
            ids["Q"][qid] = "%s:%d" % (os.path.relpath(path, rep.root), i + 1)
        marks = list(re.finditer(r"\*\*(Answer|Asked|Applied)\b[^*]*\*\*", text))
        for k, m2 in enumerate(marks):
            mark = m2.group(0)
            applied = k + 1 < len(marks) and marks[k + 1].group(1) == "Applied"
            if m2.group(1) == "Applied" and not re.fullmatch(r"\*\*Applied \(\d{4}-\d{2}-\d{2}\)\.\*\*", mark):
                rep.error(path, i + 1, "%s: not `**Applied (YYYY-MM-DD).**`: %s" % (qid, mark))
            if m2.group(1) == "Answer" and not re.match(r"\*\*Answer \(\d{4}-\d{2}-\d{2}, [^)]+\)\s*:\*\*", mark):
                rep.error(path, i + 1, "%s: answer not `**Answer (YYYY-MM-DD, who):**`: %s" % (qid, mark))
            elif (m2.group(1) == "Answer" and last_pass and not applied
                  and (mark[10:20] > last_pass or (marks_applied and mark[10:20] == last_pass))):
                rep.pending("lead-pass", path, i + 1, "%s: answered %s, not applied by the axis's last pass (%s): waits for a lead pass" % (qid, mark[10:20], last_pass))
            if m2.group(1) == "Asked" and not re.match(r"\*\*Asked \(\d{4}-\d{2}-\d{2}\), not answered\.\*\*", mark):
                rep.error(path, i + 1, "%s: not `**Asked (YYYY-MM-DD), not answered.**`: %s" % (qid, mark))
    return unnumbered


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


def marks_applied(lines, axis):
    """Whether the axis's newest skill version writes `**Applied (…).**`: under
    older ones an answer the day of the last pass says nothing either way."""
    versions = [tuple(int(n) for n in v) for v in re.findall(r"\b%s@(\d+)\.(\d+)" % re.escape(axis), "\n".join(lines))]
    return bool(versions) and max(versions) >= (0, 26)


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

    where, unsourced = {}, []
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
        sources = d.get("sources")
        if sources is not None and not isinstance(sources, dict):
            rep.error(path, d["_line"], "%s: sources must be {F-...: <hash>, ...}" % rid)
            sources = None
        if d.get("status") == "open" and fs and sources is None:
            unsourced.append(rid)
        for f in fs if d.get("status") == "open" and sources is not None else []:
            if f in findings and sources.get(f) != findings[f].sha:
                rep.pending("remediation-plan", path, d["_line"],
                            "%s: %s changed since the plan (sources %s, now %s)" % (rid, f, sources.get(f), findings[f].sha))
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
    if unsourced:
        rep.warn(path, None, "%d open fixes without `sources` (older skills): a finding changed the day of the plan does not show (%s to %s)"
                 % (len(unsourced), unsourced[0], unsourced[-1]))
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
        key = (tier(d), 0 if d.get("priority") else 1,
               -SEVERITIES.index(d["severity"]) if d.get("severity") in SEVERITIES else 0,
               EFFORTS.index(d["effort"]) if d.get("effort") in EFFORTS else 0)
        if prev is not None and key[0] < prev[1][0]:
            rep.error(path, n, "%s (tier %d) after %s (tier %d)" % (rid, key[0], prev[0], prev[1][0]))
        elif prev is not None and key[0] == prev[1][0] and key[0] == 0 and key < prev[1]:
            rep.warn(path, n, "%s after %s: not by priority, severity, then effort" % (rid, prev[0]))
        prev = (rid, key)


# --- Engagement ------------------------------------------------------------

def engagement_commit(root, rep):
    path = os.path.join(root, ENGAGEMENT)
    if not os.path.exists(path):
        rep.warn(path, None, "engagement file missing: commits not compared")
        return None
    for line in read(path):
        m = re.match(r"^commit:\s*([0-9a-f]{7,40})\b", line.strip())
        if m:
            return m.group(1)
    rep.warn(path, None, "no `commit:` in the engagement file: commits not compared")
    return None


def check_engagement(root, rep):
    path = os.path.join(root, ENGAGEMENT)
    if not os.path.exists(path):
        return
    fields = {}
    for line in read(path):
        m = re.match(r"^(owner|testing|execution):\s*(.*)$", line.strip())
        if m:
            fields.setdefault(m.group(1), strip_comment(m.group(2)).strip())
    execution = fields.get("execution")
    if execution is None or execution.startswith("<"):
        return
    if execution not in EXECUTIONS:
        rep.error(path, None, "execution `%s` not in %s" % (execution, " | ".join(EXECUTIONS)))
    elif execution != "none" and fields.get("owner", "").startswith("third party"):
        rep.error(path, None, "execution `%s` on a third party's target: only `none` is allowed" % execution)
    elif execution == "local-target" and fields.get("testing") != "active":
        rep.error(path, None, "execution `local-target` needs `testing: active`")


# --- Pointers --------------------------------------------------------------

class AuditLayout(pointers.Layout):
    """The findings files (quotes checked), then the codebase map and the plan."""

    name = VERSION
    folders = ("tool-output", "client-docs")
    clones = "repo-"

    def files(self):
        files = sorted(glob.glob(os.path.join(self.root, "findings", "*.md")))
        if not files:
            return []
        for name in (CODEBASE_MAP, PLAN):
            if os.path.exists(os.path.join(self.root, name)):
                files.append(os.path.join(self.root, name))
        return files

    def quoted(self, path):
        return os.path.dirname(path) == os.path.join(self.root, "findings")

    def roots(self):
        """The working copy, the dependency installs the map names, the workspace."""
        root, roots = self.root, []
        copy = self.repo or pointers.field(os.path.join(root, ENGAGEMENT), "working_copy")
        if copy:
            copy = os.path.expanduser(copy)
            roots.append(copy if os.path.isabs(copy) else os.path.join(root, copy))
        map_path = os.path.join(root, CODEBASE_MAP)
        if os.path.exists(map_path):
            for line in pointers.read_lines(map_path)[:20]:
                for token in re.findall(r"[\w./~-]*(?:node_modules|vendor)\b", line):
                    token = os.path.expanduser(token)
                    for base in ([token] if os.path.isabs(token) else [os.path.join(root, token)] + [os.path.join(r, token) for r in roots]):
                        if os.path.isdir(base):
                            roots.append(os.path.dirname(os.path.normpath(base)))
        roots.append(root)
        return list(dict.fromkeys(os.path.normpath(r) for r in roots))
