"""Start a review run: resolve the target, refuse an empty diff, detect the
tools, run the detectors, write the run directory.

Read-only on the reviewed repository: every git command reads objects or
refs (`rev-parse`, `merge-base`, `diff` between two commits, `ls-tree`,
`cat-file`, `log`, `config --get`), with optional locks off, and nothing is
checked out. The one write is for a PR whose head or base commit is not in
the repository yet: its objects are fetched from `origin` by ref
(`refs/pull/<n>/head`), with no ref, branch or working-copy file written.
Trees are written from git objects into the run directory, which lives
under the user's state directory, never inside the repository.
"""
import codecs
import datetime
import json
import os
import re
import shutil
import subprocess
import threading
from urllib.parse import quote

import review_format as fmt
import risk_map
import sources
from finding_core import NAME as CORE

# The run root: a fixed default under the user's state directory, not a setting.
STATE_SUBDIR = os.path.join("birdiz-review", "runs")

# Detector tools looked for on every run: (name, command). Found ones are
# recorded with their version; the adapters that use them come later.
TOOLS = [
    ("git", "git"),
    ("roave-backward-compatibility-check", "roave-backward-compatibility-check"),
    ("deptrac", "deptrac"),
    ("squawk", "squawk"),
    ("oasdiff", "oasdiff"),
    ("dependency-cruiser", "depcruise"),
    ("graphql-inspector", "graphql-inspector"),
    ("griffe", "griffe"),
    ("import-linter", "lint-imports"),
]
VERSION_RE = re.compile(r"\d+(?:\.\d+)+[\w.+-]*")
CHANGES = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "C": "copied", "T": "type-changed"}
GIT_DETECTOR = "git-changes"


class Refused(Exception):
    """The target cannot be reviewed; nothing was written."""


def state_root():
    """`$XDG_STATE_HOME/birdiz-review/runs`, `~/.local/state/...` by default."""
    base = os.environ.get("XDG_STATE_HOME", "")
    if not os.path.isabs(base):
        base = os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, STATE_SUBDIR)


# --- git, read-only ---------------------------------------------------------

def git_env():
    env = dict(os.environ)
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
    return env


def git(repo, *args, check=True, binary=False):
    done = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          stdin=subprocess.DEVNULL, env=git_env())
    if check and done.returncode != 0:
        raise Refused("git %s: %s" % (" ".join(args[:2]), done.stderr.decode("utf-8", "replace").strip()))
    if binary:
        return done.stdout
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def commit_of(repo, ref):
    if not ref or ref.startswith("-"):
        raise Refused("not a git ref: %r" % ref)
    out = git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False)
    if not out:
        raise Refused("%s is not a commit of this repository" % ref)
    return out.strip()


def default_base(repo):
    """The remote's default branch, else `main`, else `master`."""
    out = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    candidates = [out.strip()[len("refs/remotes/"):]] if out else []
    for ref in candidates + ["main", "master", "origin/main", "origin/master"]:
        if git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False):
            return ref
    raise Refused("no default branch found (origin/HEAD, main, master): give a range, <base>..<head>")


def branch_name(repo, ref):
    """The branch a ref names (a remote branch without its remote), or None."""
    full = git(repo, "rev-parse", "--symbolic-full-name", ref, check=False)
    full = (full or "").strip()
    if full.startswith("refs/heads/"):
        return full[len("refs/heads/"):]
    if full.startswith("refs/remotes/"):
        return full[len("refs/remotes/"):].split("/", 1)[-1]
    return None


def repo_name(repo):
    """`owner/name` from the origin remote, else the main working tree's name."""
    url = (git(repo, "config", "--get", "remote.origin.url", check=False) or "").strip()
    if url:
        parts = [p for p in re.split(r"[/:]", url.rstrip("/")) if p]
        if parts:
            parts[-1] = parts[-1][:-4] if parts[-1].endswith(".git") else parts[-1]
            return "/".join(parts[-2:])
    common = os.path.abspath(os.path.join(repo, git(repo, "rev-parse", "--git-common-dir").strip()))
    name = os.path.basename(common)
    return os.path.basename(os.path.dirname(common)) if name == ".git" else name[:-4] if name.endswith(".git") else name


def key(text):
    """One path component: every character but letters, digits, `.`, `_`, `-` escaped."""
    k = quote(text, safe="")
    return "%2E" + k[1:] if k.startswith(".") else k


def branch_runs(repo, branch):
    """The directory holding one run directory per reviewed head of `branch`
    (`<run root>/<repo>/<branch>/`); it may not exist. A branch has been
    reviewed when one of its subdirectories holds a `run.json`."""
    return os.path.join(state_root(), key(repo_name(repo)), key(branch))


def read_risk_map(repo, sha):
    """The risk map of `docs/agents/review.md` as committed at `sha`, read
    from git objects. The base's copy, so a branch can't narrow its own."""
    rm = {"path": risk_map.PATH, "sha": sha, "found": False, "stacks": [], "rows": [], "problems": []}
    blob = git(repo, "cat-file", "blob", "%s:%s" % (sha, risk_map.PATH), check=False, binary=True)
    if not blob:
        return rm
    stacks, rows, problems = risk_map.parse(blob.decode("utf-8", "replace"))
    rm.update({"found": True, "stacks": stacks,
               "rows": [{"glob": g, "zone": z} for g, z, _ in rows],
               "problems": [{"line": n, "message": m} for n, m in problems]})
    return rm


def has_commit(repo, sha):
    return bool(git(repo, "cat-file", "-e", sha + "^{commit}", check=False) is not None)


def ensure_commit(repo, sha, ref):
    """Fetch `ref` from origin when `sha` is not in the repository: objects
    only, no ref written (`--no-write-fetch-head` where git has it).
    Returns the ref fetched, or None when nothing was needed."""
    if has_commit(repo, sha):
        return None
    for flags in (["--no-write-fetch-head"], []):
        git(repo, "fetch", "--quiet", "--no-tags", *flags, "origin", ref, check=False)
        if has_commit(repo, sha):
            return ref
    raise Refused("%s (%s) is not in this repository and could not be fetched from origin" % (sha[:12], ref))


def resolve_pr(repo, number, forge):
    """The run's target for a pull request, read with the forge, and the PR."""
    if not forge.available():
        raise Refused("a PR number is read with gh, which is not found on this machine: give a branch or a range")
    try:
        data = forge.pr(number) or {}
    except sources.ForgeError as e:
        raise Refused("PR #%s: %s" % (number, e))
    head_sha, base_ref = data.get("headRefOid"), data.get("baseRefName")
    if not head_sha or not base_ref:
        raise Refused("PR #%s: gh gave no head or base" % number)
    fetched = [ensure_commit(repo, head_sha, "refs/pull/%s/head" % number)]
    base_sha = data.get("baseRefOid")
    if base_sha:
        fetched.append(ensure_commit(repo, base_sha, "refs/heads/%s" % base_ref))
    else:
        base_sha = commit_of(repo, "origin/%s" % base_ref)
    mb = git(repo, "merge-base", base_sha, head_sha, check=False)
    if not mb:
        raise Refused("PR #%s: its base and head share no history" % number)
    head_ref = data.get("headRefName") or "pr-%s" % number
    target = {
        "target": "%s..%s" % (base_ref, head_ref),
        "base": {"ref": base_ref, "sha": base_sha},
        "head": {"ref": head_ref, "sha": head_sha},
        "merge_base": mb.strip(),
        "branch": head_ref,
    }
    pr = {"number": data.get("number", number), "url": data.get("url"), "title": data.get("title"),
          "state": data.get("state"), "base": base_ref, "head": head_ref,
          "fetched": [f for f in fetched if f]}
    body = {"body": data.get("body") or "", "repo": repo_name(repo),
            "closing": [i["number"] for i in data.get("closingIssuesReferences") or []
                        if isinstance(i, dict) and i.get("number")]}
    return target, pr, body


def resolve(repo, target):
    """The run's target: base, head, merge base, branch."""
    if "..." in target:
        base, head = target.split("...", 1)
    elif ".." in target:
        base, head = target.split("..", 1)
    else:
        base, head = None, target
    if base is not None and (not base or not head):
        raise Refused("a range needs both ends: <base>..<head>")
    head_sha = commit_of(repo, head)
    base = base or default_base(repo)
    base_sha = commit_of(repo, base)
    mb = git(repo, "merge-base", base_sha, head_sha, check=False)
    if not mb:
        raise Refused("%s and %s share no history" % (base, head))
    return {
        "target": target if ".." in target else "%s..%s" % (base, head),
        "base": {"ref": base, "sha": base_sha},
        "head": {"ref": head, "sha": head_sha},
        "merge_base": mb.strip(),
        "branch": branch_name(repo, head) or head,
    }


# --- Detectors --------------------------------------------------------------

def tool_version(path, cwd):
    try:
        done = subprocess.run([path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, cwd=cwd, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    m = VERSION_RE.search(done.stdout.decode("utf-8", "replace"))
    return m.group(0) if m else "unknown"


def detect_tools(cwd):
    """Every detector tool looked for, found or not, with its version."""
    out = []
    for name, command in TOOLS:
        path = shutil.which(command)
        if path:
            out.append({"name": name, "command": command, "found": True, "version": tool_version(path, cwd)})
        else:
            out.append({"name": name, "command": command, "found": False})
    return out


def changes(repo, base, head):
    """[(change, path, from)] between two commits, renames detected."""
    raw = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--name-status", "-z", "-M", base, head)
    tokens = raw.split("\0")
    out, i = [], 0
    while i < len(tokens) and tokens[i]:
        status = tokens[i]
        letter = status[0]
        if letter in "RC":
            out.append((CHANGES[letter], tokens[i + 2], tokens[i + 1], status[1:]))
            i += 3
        else:
            out.append((CHANGES.get(letter, "changed"), tokens[i + 1], None, None))
            i += 2
    return out


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def patch(repo, base, head):
    """The unified diff between two commits, renames detected, as bytes:
    what the judgment steps read as `diff.patch`."""
    return git(repo, "-c", "core.quotePath=false", "diff", "--no-ext-diff", "--no-textconv", "--no-color",
               "-M", base, head, binary=True)


def _patch_path(text, side):
    """The path of a `--- a/x` / `+++ b/x` header line, None for /dev/null."""
    text = text.rstrip("\n").split("\t", 1)[0]
    if text == "/dev/null":
        return None
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = codecs.escape_decode(text[1:-1].encode("utf-8"))[0].decode("utf-8", "replace")
    return text[2:] if text.startswith(side + "/") else text


def hunks(patch_bytes):
    """{path: [[start, count]]}: the new-side line range of each hunk of the
    patch, per file (the old path for a deleted file, whose ranges are
    empty)."""
    out, path, old, in_header = {}, None, None, False
    for raw in patch_bytes.decode("utf-8", "replace").split("\n"):
        if raw.startswith("diff --git "):
            path, old, in_header = None, None, True
        elif in_header and raw.startswith("--- "):
            old = _patch_path(raw[4:], "a")
        elif in_header and raw.startswith("+++ "):
            path = _patch_path(raw[4:], "b") or old
            out.setdefault(path, [])
        elif raw.startswith("@@"):
            in_header = False
            m = HUNK.match(raw)
            if m and path is not None:
                start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
                if count or start:
                    out[path].append([start, count])
    return out


def git_changes(repo, target, git_version, ranges=None):
    """The git file-change signals: added, deleted, renamed files and new
    directories, and the new-side line ranges of each file's hunks.
    Stack-agnostic, so not a content detector: it says a file changed in a
    notable way, not what the change means."""
    base, head = target["merge_base"], target["head"]["sha"]
    files = changes(repo, base, head)
    ranges = ranges or {}
    base_dirs = set(git(repo, "ls-tree", "-r", "-d", "-z", "--name-only", base).split("\0"))
    new_dirs = set()
    for change, path, _, _ in files:
        if change in ("added", "renamed", "copied"):
            d = os.path.dirname(path)
            while d and d not in base_dirs:
                new_dirs.add(d)
                d = os.path.dirname(d)
    entries, signals = [], []
    for change, path, origin, score in files:
        entry = {"path": path, "change": change}
        if origin:
            entry["from"], entry["similarity"] = origin, int(score or 0)
        entry["hunks"] = [] if change == "deleted" else ranges.get(path, [])
        entries.append(entry)
        if change == "modified":
            continue
        reason = {"renamed": "renamed from `%s`" % origin, "copied": "copied from `%s`" % origin}.get(change, change)
        top = [d for d in sorted(new_dirs) if path.startswith(d + "/") and os.path.dirname(d) not in new_dirs]
        if change != "deleted" and top:
            reason += " in a new directory `%s/`" % top[0]
        signals.append({"path": path, "kind": change, "reason": reason})
    return {
        "detector": GIT_DETECTOR, "version": fmt.VERSION, "content": False, "applies_to": ["*"],
        "tool": "git@%s" % git_version, "heuristic": False, "diff": diff_of(target),
        "files": entries, "new_directories": sorted(new_dirs),
        "covered": [e["path"] for e in entries], "not_covered": [], "signals": signals,
    }


def diff_of(target):
    return "%s..%s" % (target["merge_base"][:12], target["head"]["sha"][:12])


def extract_tree(repo, sha, dest):
    """Write a commit's tree from git objects: regular files only; symlinks
    and submodules are listed, not followed. Returns what was skipped."""
    listing = git(repo, "ls-tree", "-r", "-z", "--full-tree", sha, binary=True).split(b"\0")
    blobs, skipped = [], []
    for item in listing:
        if not item:
            continue
        meta, path = item.split(b"\t", 1)
        mode, kind, obj = meta.split(b" ")
        rel = path.decode("utf-8", "surrogateescape")
        parts = rel.split("/")
        if os.path.isabs(rel) or ".." in parts or ".git" in parts:
            skipped.append(rel)
        elif kind == b"blob" and mode in (b"100644", b"100755"):
            blobs.append((obj, rel))
        else:
            skipped.append(rel)
    if not blobs:
        return skipped
    proc = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=git_env())

    def feed():  # in its own thread: git stops reading while its output is not read
        try:
            for obj, _ in blobs:
                proc.stdin.write(obj + b"\n")
        finally:
            proc.stdin.close()

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    for obj, rel in blobs:
        header = proc.stdout.readline().split()
        if len(header) != 3:
            skipped.append(rel)
            continue
        data = proc.stdout.read(int(header[2]))
        proc.stdout.read(1)
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(data)
    writer.join()
    proc.wait()
    return skipped


# --- The run directory --------------------------------------------------------

def inside(path, top):
    path, top = os.path.realpath(path), os.path.realpath(top)
    return path == top or path.startswith(top.rstrip(os.sep) + os.sep)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=False)
        fh.write("\n")


def start(repo_arg, target_arg, now=None, pr=None, spec=None, no_spec=False, forge=None):
    """Write a run directory for the target, a branch or a range, or for the
    pull request numbered `pr`; returns (run directory, run). `spec` and
    `no_spec` are the user's answer when the spec could not be found."""
    top = git(repo_arg, "rev-parse", "--show-toplevel", check=False)
    if not top:
        raise Refused("%s is not inside a git repository" % repo_arg)
    repo = top.strip()
    common = os.path.abspath(os.path.join(repo, git(repo, "rev-parse", "--git-common-dir").strip()))
    forge = forge or sources.GitHub(repo)
    pr_header, pr_body = None, None
    if pr is not None:
        target, pr_header, pr_body = resolve_pr(repo, pr, forge)
    else:
        target = resolve(repo, target_arg)
    files = changes(repo, target["merge_base"], target["head"]["sha"])
    if not files:
        raise Refused("empty diff: %s changes nothing against %s (merge base %s), nothing to review"
                      % (target["head"]["ref"], target["base"]["ref"], target["merge_base"][:12]))

    root = state_root()
    for top_ in (repo, common, os.path.dirname(common) if os.path.basename(common) == ".git" else common):
        if inside(root, top_):
            raise Refused("the run root %s is inside the reviewed repository %s" % (root, top_))
    name = repo_name(repo)
    head12 = target["head"]["sha"][:12]
    branch_dir = branch_runs(repo, target["branch"])
    final = os.path.join(branch_dir, head12)
    if os.path.exists(final) and not os.path.isfile(os.path.join(final, fmt.HEADER)):
        raise Refused("%s exists and is not a run directory: left as it is" % final)
    os.makedirs(branch_dir, exist_ok=True)
    tmp = os.path.join(branch_dir, ".%s.tmp-%d" % (head12, os.getpid()))
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    try:
        tools = detect_tools(tmp)
        git_version = next(t.get("version") for t in tools if t["name"] == "git")
        os.makedirs(os.path.join(tmp, fmt.SIGNALS))
        rel = "%s/%s.json" % (fmt.SIGNALS, GIT_DETECTOR)
        diff_bytes = patch(repo, target["merge_base"], target["head"]["sha"])
        with open(os.path.join(tmp, fmt.PATCH), "wb") as fh:
            fh.write(diff_bytes)
        write_json(os.path.join(tmp, rel), git_changes(repo, target, git_version, hunks(diff_bytes)))
        skipped = extract_tree(repo, target["head"]["sha"], os.path.join(tmp, fmt.TREE + head12))
        found = sources.gather(repo, tmp, target, dict(pr_header, **pr_body) if pr_header else None,
                               spec, no_spec, forge)
        header = {
            "schema": fmt.VERSION, "core": CORE, "repo": name, "branch": target["branch"],
            "target": target["target"], "base": target["base"], "head": target["head"],
            "merge_base": target["merge_base"], "diff": diff_of(target),
            "started": (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": tools, "detectors": [rel],
            "trees": {"head": fmt.TREE + head12, "skipped": skipped},
            "steps_in_version": list(fmt.STEPS_IN_VERSION),
            "risk_map": read_risk_map(repo, target["base"]["sha"]),
            "sources": sources.SOURCES,
            "patch": fmt.PATCH,
        }
        if pr_header:
            header["pr"] = pr_header
        write_json(os.path.join(tmp, fmt.HEADER), header)
        os.makedirs(os.path.join(tmp, fmt.FINDINGS))
        changed = [path for _, path, _, _ in files]
        for axis in fmt.AXES:
            with open(os.path.join(tmp, fmt.FINDINGS, axis + ".md"), "w", encoding="utf-8") as fh:
                fh.write(fmt.findings_at_start(axis, found, changed))
        if os.path.exists(final):
            shutil.rmtree(final)
        os.rename(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    run = fmt.Run(final)
    with open(os.path.join(final, fmt.BRIEF), "w", encoding="utf-8") as fh:
        fh.write(fmt.render_brief(run))
    return final, run
