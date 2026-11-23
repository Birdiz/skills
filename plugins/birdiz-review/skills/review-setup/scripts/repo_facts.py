"""What `review-setup` finds in a repository, and how it writes.

Detection reads the repository and this machine and writes nothing:
- stacks, from manifests and file extensions;
- detector tools on this machine (reported, never stored);
- the Pocock artifacts the review reads, and their shape;
- risk zones, each with a pointer to what suggested it;
- whether writing is allowed now (the write guard).

Writing installs `docs/agents/review.md` and the `### Review` subsection of
the `## Agent skills` block, and nothing else.

Standard library only, Python 3.8 or later; external tools only when present.
`risk_map` and `review_run` are review-pr's: the entry points put its
scripts and the plugin's copy of the finding core on the path.
"""
import json
import os
import re
import shutil
import subprocess

import review_run  # review-pr's run layout
import risk_map  # the format of review.md, which review-pr reads

AGENT_FILES = ("CLAUDE.md", "AGENTS.md")       # Pocock's setup edits CLAUDE.md first
TRACKER_DOC = "docs/agents/issue-tracker.md"
DOMAIN_DOC = "docs/agents/domain.md"
SUBSECTION = "### Review"
SUBSECTION_BODY = "Stacks and risk map for the review skills. See `docs/agents/review.md`."

SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build",
             "tests", "test", "__tests__", "spec", "specs", "fixtures", "docs", ".scratch"}
MAX_PROPOSALS = 12      # per zone; the rest are counted, not listed
MAX_BYTES = 256 * 1024  # content signals skip larger files


# ---------------------------------------------------------------- files

def _git(repo, *args):
    try:
        done = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
    except OSError as exc:
        return 127, "", str(exc)
    return done.returncode, done.stdout, done.stderr.strip()


def list_files(repo):
    """Repository-relative paths, tracked and untracked but not ignored.
    Falls back to a walk when the directory is not a git work tree."""
    code, out, _ = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if code == 0:
        return sorted(p for p in set(out.split("\0")) if p and os.path.isfile(os.path.join(repo, p)))
    found = []
    for d, dirs, files in os.walk(repo):
        dirs[:] = sorted(x for x in dirs if x != ".git")
        for f in files:
            found.append(os.path.relpath(os.path.join(d, f), repo).replace(os.sep, "/"))
    return sorted(found)


def _read(repo, rel, limit=None, raw=False):
    try:
        with open(os.path.join(repo, rel), encoding="utf-8", errors="replace",
                  newline="" if raw else None) as fh:
            return fh.read(limit) if limit else fh.read()
    except OSError:
        return None


# ---------------------------------------------------------------- stacks

STACKS = (
    # name, manifest names, extensions
    ("php", ("composer.json",), (".php",)),
    ("typescript", ("tsconfig.json",), (".ts", ".tsx", ".mts", ".cts")),
    ("javascript", (), (".js", ".jsx", ".mjs", ".cjs")),
    ("python", ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"), (".py",)),
    ("go", ("go.mod",), (".go",)),
    ("ruby", ("Gemfile",), (".rb",)),
    ("java", ("pom.xml", "build.gradle", "build.gradle.kts"), (".java", ".kt")),
    ("rust", ("Cargo.toml",), (".rs",)),
)


def _skipped(path):
    return any(part in SKIP_DIRS for part in path.split("/")[:-1])


def detect_stacks(files):
    """[{name, pointer}]: a manifest, else the count of source files."""
    out = []
    for name, manifests, exts in STACKS:
        manifest = next((f for f in files if f.split("/")[-1] in manifests and not _skipped(f)), None)
        sources = [f for f in files if f.endswith(exts) and not _skipped(f)]
        if name == "javascript" and any(s["name"] == "typescript" for s in out) and not sources:
            continue
        if manifest and (sources or name in ("php", "python", "go", "rust")):
            out.append({"name": name, "pointer": manifest})
        elif sources:
            out.append({"name": name, "pointer": "%d %s file(s), e.g. %s" % (len(sources), "/".join(exts), sources[0])})
    return out


# ---------------------------------------------------------------- tools

TOOLS = (
    # name, stack, executables, repo-local paths
    ("git", "any", ("git",), ()),
    ("gh", "any", ("gh",), ()),
    ("roave-backward-compatibility-check", "php", ("roave-backward-compatibility-check",),
     ("vendor/bin/roave-backward-compatibility-check",)),
    ("deptrac", "php", ("deptrac",), ("vendor/bin/deptrac",)),
    ("squawk", "sql", ("squawk",), ("node_modules/.bin/squawk",)),
    ("oasdiff", "openapi", ("oasdiff",), ()),
    ("dependency-cruiser", "typescript", ("depcruise",), ("node_modules/.bin/depcruise",)),
    ("graphql-inspector", "graphql", ("graphql-inspector",), ("node_modules/.bin/graphql-inspector",)),
    ("griffe", "python", ("griffe",), (".venv/bin/griffe",)),
    ("import-linter", "python", ("lint-imports",), (".venv/bin/lint-imports",)),
)


def detect_tools(repo):
    """[{name, stack, found, where}]: on PATH or installed in the repository.
    Nothing is run: versions belong in a review run's header, not here."""
    out = []
    for name, stack, exes, local in TOOLS:
        where = next((shutil.which(e) for e in exes if shutil.which(e)), None)
        if not where:
            where = next((p for p in local if os.path.isfile(os.path.join(repo, p))), None)
        out.append({"name": name, "stack": stack, "found": bool(where), "where": where})
    return out


# ---------------------------------------------------------------- Pocock artifacts

def _headings(text):
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


def agent_skills_file(repo):
    """(file, text, start, end) of the `## Agent skills` block: start is the
    heading's line index, end the index of the next heading of level 1 or 2
    (or the line count). None when no candidate holds the block."""
    for name in AGENT_FILES:
        text = _read(repo, name, raw=True)
        if text is None:
            continue
        lines = text.splitlines()
        hs = _headings(text)
        for i, (level, title, no) in enumerate(hs):
            if level == 2 and title.lower() == "agent skills":
                end = next((n - 1 for lv, _, n in hs[i + 1:] if lv <= 2), len(lines))
                return name, text, no - 1, end
    return None


def check_pocock(repo):
    """[{artifact, path, status, detail}], status one of
    ok | missing | drift | unchecked | absent (absent is not drift)."""
    out = []

    def add(artifact, path, status, detail):
        out.append({"artifact": artifact, "path": path, "status": status, "detail": detail})

    block = agent_skills_file(repo)
    if block is None:
        present = [n for n in AGENT_FILES if os.path.isfile(os.path.join(repo, n))]
        add("agent skills block", " or ".join(AGENT_FILES), "missing",
            "no `## Agent skills` block in %s; run Pocock's `setup-matt-pocock-skills` first"
            % (" or ".join(present) if present else "CLAUDE.md or AGENTS.md (neither exists)"))
    else:
        name, text, start, end = block
        subs = {t.lower() for lv, t, n in _headings(text) if lv == 3 and start < n - 1 < end}
        lacking = [s for s in ("issue tracker", "domain docs") if s not in subs]
        if lacking:
            add("agent skills block", name, "drift",
                "`## Agent skills` has no %s subsection" % " or ".join("`### %s`" % s.title() for s in lacking))
        else:
            add("agent skills block", name, "ok", "`## Agent skills` with Issue tracker and Domain docs")

    text = _read(repo, TRACKER_DOC)
    if text is None:
        add("tracker doc", TRACKER_DOC, "missing", "the review can't read the spec and tickets without it")
    else:
        hs = _headings(text)
        title = next((t for lv, t, _ in hs if lv == 1), "")
        m = re.match(r"(?i)^issue tracker:\s*(.+)$", title)
        kind = m.group(1).strip() if m else None
        if kind and kind.lower() in ("github", "gitlab", "local markdown"):
            if any(lv == 2 and re.search(r"(?i)fetch the relevant ticket", t) for lv, t, _ in hs):
                add("tracker doc", TRACKER_DOC, "ok", "%s tracker with a \"fetch the relevant ticket\" section" % kind)
            else:
                add("tracker doc", TRACKER_DOC, "drift",
                    "%s tracker without a `## When a skill says \"fetch the relevant ticket\"` section" % kind)
        else:
            add("tracker doc", TRACKER_DOC, "unchecked",
                "freeform tracker (%s): its shape has no template to check" % (
                    "`# Issue tracker: %s`" % kind if kind else "no `# Issue tracker: <kind>` title"))

    text = _read(repo, DOMAIN_DOC)
    if text is None:
        add("domain doc", DOMAIN_DOC, "missing", "the review can't find the glossary and ADRs without it")
        return out
    legacy = sorted(set(re.findall(r"\bCONTEXT(?:-MAP)?\.md\b", text)))
    names_glossary = "GLOSSARY.md" in text
    # "there is no GLOSSARY-MAP.md" mentions the map without naming it
    names_map = "GLOSSARY-MAP.md" in text and (
        not names_glossary or os.path.isfile(os.path.join(repo, "GLOSSARY-MAP.md")))
    adr_dirs = sorted(set(re.findall(r"`?((?:[\w.<>-]+/)*adr)/`?", text)))
    problems = []
    if legacy:
        problems.append("names legacy %s; the review reads GLOSSARY.md / GLOSSARY-MAP.md" % ", ".join(legacy))
    if not (names_glossary or names_map):
        problems.append("names no GLOSSARY.md or GLOSSARY-MAP.md")
    if not adr_dirs:
        problems.append("names no ADR directory (e.g. docs/adr/)")
    if problems:
        add("domain doc", DOMAIN_DOC, "drift", "; ".join(problems))
    else:
        add("domain doc", DOMAIN_DOC, "ok", "names %s and %s" % (
            "GLOSSARY-MAP.md" if names_map else "GLOSSARY.md", ", ".join(d + "/" for d in adr_dirs)))
    if names_map and os.path.isfile(os.path.join(repo, "GLOSSARY-MAP.md")):
        add("glossary", "GLOSSARY-MAP.md", "ok", "multi-context glossary map")
    elif os.path.isfile(os.path.join(repo, "GLOSSARY.md")):
        add("glossary", "GLOSSARY.md", "ok", "single-context glossary")
    else:
        add("glossary", "GLOSSARY.md", "absent",
            "not created yet (Pocock creates it lazily): glossary checks will be not-evaluable")
    root_adr = next((d for d in adr_dirs if "<" not in d and os.path.isdir(os.path.join(repo, d))), None)
    if root_adr:
        add("ADRs", root_adr + "/", "ok", "%d file(s)" % len(os.listdir(os.path.join(repo, root_adr))))
    else:
        add("ADRs", (adr_dirs[0] if adr_dirs else "docs/adr") + "/", "absent",
            "not created yet (Pocock creates them lazily): ADR checks will be not-evaluable")
    return out


# ---------------------------------------------------------------- risk zones

def _words(*names):
    return re.compile(r"^(?:%s)$" % "|".join(names))


DIR_SIGNALS = (
    ("auth", _words("auth", "authn", "authz", "authentication", "authorization", "security", "login",
                    "oauth", "oauth2", "sso", "jwt", "acl", "permissions?", "guards?", "voters?", "policies")),
    ("personal-data", _words("users?", "customers?", "accounts?", "profiles?", "members?", "patients?",
                             "contacts?", "gdpr", "privacy", "consents?", "pii")),
    ("payments", _words("payments?", "billing", "invoices?", "invoicing", "checkout", "subscriptions?",
                        "stripe", "paypal", "wallets?", "refunds?")),
    ("concurrency", _words("queues?", "workers?", "jobs?", "messenger", "consumers?", "schedulers?",
                           "cron", "locks?", "locking")),
    ("irreversible", _words("migrations?", "migrate")),
    ("public-api", _words("api", "controllers?", "routes?", "routing", "graphql", "endpoints?", "webhooks?")),
)
FILE_SIGNALS = (
    ("auth", re.compile(r"^(security\.ya?ml|.*(voter|authenticator|guard)\.(php|ts|js|py))$", re.I)),
    ("personal-data", re.compile(r"^(user|customer|account|profile|member|patient|contact|person|employee)"
                                 r"s?\.(php|py|ts|js|rb|go|java|kt)$", re.I)),
    ("payments", re.compile(r"^(payment|billing|invoice|checkout|subscription|stripe)s?\.\w+$", re.I)),
    ("irreversible", re.compile(r"^.*\.sql$", re.I)),
    ("public-api", re.compile(r"^(openapi|swagger)\.(ya?ml|json)$|^.*\.(graphql|gql|proto)$|"
                              r"^(routes?|urls)\.(php|py|ts|js|ya?ml|rb)$", re.I)),
)
CONTENT_EXTS = (".php", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sql", ".rb", ".go",
                ".java", ".kt", ".cs")
CONTENT_SIGNALS = (
    ("auth", re.compile(r"password_hash\(|password_verify\(|\bbcrypt\b|\bJWT::(?:encode|decode)|"
                        r"\bjwt\.(?:encode|decode|sign|verify)\(|@login_required|#\[IsGranted|isGranted\(")),
    ("payments", re.compile(r"\\Stripe\\|^\s*(?:from|import)\s+stripe\b|require\(['\"]stripe['\"]\)|"
                            r"from\s+['\"]stripe['\"]|\bbraintree\b|\bAdyen\\|\bMollie\\", re.M)),
    ("concurrency", re.compile(r"\bflock\(|\bFOR UPDATE\b|\bLockFactory\b|^\s*import threading\b|"
                               r"\bmultiprocessing\b|asyncio\.Lock\(|new Worker\(|\bMutex\b|\bSemaphore\b", re.M)),
    ("irreversible", re.compile(r"\bDROP\s+(?:TABLE|COLUMN|DATABASE|SCHEMA)\b|\bTRUNCATE\s+TABLE\b|"
                                r"\bdropColumn\(|\bdropTable\(|\bop\.drop_(?:table|column)\(", re.I)),
    ("public-api", re.compile(r"#\[Route\(|@Route\(|@(?:app|router|bp|api)\.(?:get|post|put|patch|delete|route)\(|"
                              r"\b(?:router|app)\.(?:get|post|put|patch|delete)\(['\"]")),
)


def _quote(line):
    s = line.strip()
    return s if len(s) <= 80 else s[:77] + "..."


def propose_zones(repo, files):
    """[{zone, glob, pointer, why}] in zone order, then glob order.

    A directory whose name suggests a zone gives `<dir>/**`; a file name or a
    line of content gives the file itself, unless a directory proposal of the
    same zone already covers it."""
    by_zone = {z: {} for z in risk_map.ZONES}
    for path in files:
        if _skipped(path):
            continue
        parts = path.split("/")
        for zone, rx in DIR_SIGNALS:
            for k, part in enumerate(parts[:-1]):
                if rx.match(re.sub(r"[^a-z0-9]", "", part.lower())):
                    d = "/".join(parts[:k + 1])
                    entry = by_zone[zone].setdefault(d + "/**", {"files": 0, "why": "directory name", "dir": d})
                    entry["files"] += 1
                    break
        for zone, rx in FILE_SIGNALS:
            if rx.match(parts[-1]):
                by_zone[zone].setdefault(path, {"pointer": path, "why": "file name"})
        if path.endswith(CONTENT_EXTS):
            try:
                if os.path.getsize(os.path.join(repo, path)) > MAX_BYTES:
                    continue
            except OSError:
                continue
            text = _read(repo, path)
            if not text:
                continue
            for zone, rx in CONTENT_SIGNALS:
                m = rx.search(text)
                if m:
                    no = text.count("\n", 0, m.start()) + 1
                    line = text.splitlines()[no - 1] if text.splitlines() else ""
                    by_zone[zone].setdefault(path, {"pointer": '%s:%d "%s"' % (path, no, _quote(line)),
                                                    "why": "content"})
    out = []
    for zone in risk_map.ZONES:
        entries = by_zone[zone]
        dirs = sorted(g for g, e in entries.items() if "dir" in e)
        # keep the outermost directory of a nest
        outer = [g for g in dirs if not any(g != o and g.startswith(o[:-2] + "/") for o in dirs)]
        covers = [risk_map.compile_glob(g) for g in outer]
        chosen = []
        for g in outer:
            e = entries[g]
            chosen.append({"zone": zone, "glob": g, "why": e["why"],
                           "pointer": "%s/ (%d file(s))" % (e["dir"], e["files"])})
        for g in sorted(x for x, e in entries.items() if "dir" not in e):
            if any(c(g) for c in covers):
                continue
            chosen.append({"zone": zone, "glob": g, "why": entries[g]["why"], "pointer": entries[g]["pointer"]})
        if len(chosen) > MAX_PROPOSALS:
            rest = len(chosen) - MAX_PROPOSALS
            chosen = chosen[:MAX_PROPOSALS]
            chosen.append({"zone": zone, "glob": None, "why": "truncated",
                           "pointer": "%d more candidate(s) not listed" % rest})
        out.extend(chosen)
    return out


# ---------------------------------------------------------------- write guard

def run_dirs_for(repo, branch):
    """review-pr run directories of `branch` in this repository: the
    subdirectories of review_run.branch_runs() that hold a run.json (hidden
    ones are unfinished runs)."""
    d = review_run.branch_runs(repo, branch)
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, x) for x in sorted(os.listdir(d))
            if not x.startswith(".") and os.path.isfile(os.path.join(d, x, "run.json"))]


def write_guard(repo, use_gh=True):
    """{allowed, branch, reasons, checks}: writing is refused while a branch
    under review is checked out (detached HEAD, head of an open PR, or a
    branch review-pr has a run directory for)."""
    reasons, checks = [], []
    code, out, err = _git(repo, "rev-parse", "--is-inside-work-tree")
    if code != 0 or out.strip() != "true":
        return {"allowed": False, "branch": None, "checks": checks,
                "reasons": ["not a git work tree: %s" % (err or "git not found")]}
    code, out, _ = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    branch = out.strip() if code == 0 else None
    if branch is None:
        reasons.append("HEAD is detached (a reviewed PR is often checked out this way); "
                       "switch to a branch of your own")
        return {"allowed": False, "branch": None, "checks": checks, "reasons": reasons}
    gh = shutil.which("gh") if use_gh else None
    if gh:
        try:
            done = subprocess.run([gh, "pr", "list", "--head", branch, "--state", "open",
                                   "--json", "number,url"], cwd=repo, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
            if done.returncode == 0:
                prs = json.loads(done.stdout or "[]")
                checks.append("open PRs: checked with gh, %d found" % len(prs))
                for pr in prs:
                    reasons.append("`%s` is the head of open PR #%s (%s)" % (branch, pr.get("number"), pr.get("url")))
            else:
                checks.append("open PRs: not checked (gh: %s)" % (done.stderr.strip().splitlines() or ["failed"])[-1])
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            checks.append("open PRs: not checked (gh: %s)" % exc)
    else:
        checks.append("open PRs: not checked (%s)" % ("gh not found" if use_gh else "--no-gh"))
    runs = run_dirs_for(repo, branch)
    checks.append("review runs: %d for `%s` under %s" % (len(runs), branch, review_run.state_root()))
    if runs:
        reasons.append("review-pr has reviewed `%s` (%s)" % (branch, runs[-1]))
    return {"allowed": not reasons, "branch": branch, "checks": checks, "reasons": reasons}


# ---------------------------------------------------------------- writing

def with_review_subsection(text, start, end, body=SUBSECTION_BODY):
    """`text` with `### Review` set inside the `## Agent skills` block that
    spans lines [start, end): replaced in place when it exists, appended at
    the end of the block otherwise. Other lines are kept byte for byte."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += newline
    block_text = "".join(lines[start:end])
    subs = [(lv, t, start + n - 1) for lv, t, n in _headings(block_text) if lv >= 3]
    new = [SUBSECTION + newline, newline, body + newline]
    for i, (lv, title, idx) in enumerate(subs):
        if lv == 3 and title.lower() == "review":
            stop = next((j for l2, _, j in subs[i + 1:] if l2 <= 3), end)
            tail = lines[idx:stop]
            # keep the blank lines that separated it from what follows
            trailing = len(tail) - len(("".join(tail)).rstrip("\r\n").splitlines(True))
            return "".join(lines[:idx] + new + [newline] * trailing + lines[stop:])
    last = end
    while last > start + 1 and not lines[last - 1].strip():
        last -= 1
    after = lines[last:end]
    insert = [newline] + new + (after if after else ([newline] if end < len(lines) else []))
    return "".join(lines[:last] + insert + lines[end:])


def write(repo, stacks, rows, use_gh=True):
    """Install review.md and the `### Review` subsection. Returns
    (written paths, refusal reasons): nothing is written when there are reasons."""
    reasons = []
    for s in stacks:
        if not risk_map.STACK_NAME.match(s):
            reasons.append("stack %r is not a lowercase name" % s)
    seen = set()
    for glob, zone in rows:
        why = risk_map.glob_problem(glob)
        if why:
            reasons.append("glob %r: %s" % (glob, why))
        if not risk_map.ZONE_NAME.match(zone):
            reasons.append("zone %r is not a lowercase-hyphen name" % zone)
        if (glob, zone) in seen:
            reasons.append("row %s -> %s is listed twice" % (glob, zone))
        seen.add((glob, zone))
    block = agent_skills_file(repo)
    if block is None:
        reasons.append("no `## Agent skills` block in CLAUDE.md or AGENTS.md: "
                       "run Pocock's `setup-matt-pocock-skills` first")
    guard = write_guard(repo, use_gh=use_gh)
    reasons.extend(guard["reasons"])
    if reasons:
        return [], reasons
    name, text, start, end = block
    target = os.path.join(repo, *risk_map.PATH.split("/"))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(risk_map.render(stacks, rows))
    updated = with_review_subsection(text, start, end)
    written = [risk_map.PATH]
    if updated != text:
        with open(os.path.join(repo, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(updated)
        written.append(name)
    return written, []
