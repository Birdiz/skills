"""What the reviewed change was supposed to do: the PR body, the spec and the
tickets, found in a fixed order and each checked against the Pocock
contract when it is read.

Order, first match wins:
1. the spec or ticket the user named (`--spec`), or none (`--no-spec`);
2. the closing references in the PR body (which `implement-spec` writes);
3. issue references in the commit messages of the diff (merges left out);
4. a spec file under `docs/`, `specs/` or `.scratch/` of the head tree
   whose path names the branch;
5. nothing: the run says so, and the skill asks the user.

Issues are read through the tracker the tracker doc names, as committed at
the base: GitHub with `gh`, local markdown from the head tree. A ticket's
parent is its spec; a spec's tickets are its sub-issues, else the issues
with a `Part of #<spec>` line, else the `issues/` files beside a local spec.

Every artifact read is copied into `sources/` of the run directory and
recorded in `sources.json`. Read-only on the repository: git objects and
the forge, nothing checked out.
"""
import json
import os
import re
import shutil
import subprocess

import pocock

SOURCES_DIR = "sources"
SOURCES = "sources.json"
SPEC_ROOTS = ("docs", "specs", ".scratch")
EVALUABLE = "evaluable"
GH_ISSUE_FIELDS = "number,title,body,state,url,labels"
GH_PR_FIELDS = ("number,title,body,url,state,baseRefName,baseRefOid,headRefName,headRefOid,"
                "closingIssuesReferences")


class ForgeError(Exception):
    pass


class GitHub:
    """The `gh` calls the review makes, all reads. Runs in the repository,
    so `gh` infers the repository from its remote."""

    def __init__(self, repo):
        self.repo = repo
        self.path = shutil.which("gh")

    def available(self):
        return self.path is not None

    def call(self, *args):
        if not self.path:
            raise ForgeError("gh not found")
        try:
            done = subprocess.run([self.path] + list(args), cwd=self.repo, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=60,
                                  env=dict(os.environ, GH_PROMPT_DISABLED="1", NO_COLOR="1"))
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ForgeError("gh %s: %s" % (" ".join(args[:2]), e))
        if done.returncode != 0:
            err = done.stderr.decode("utf-8", "replace").strip().splitlines()
            raise ForgeError("gh %s: %s" % (" ".join(args[:3]), err[-1] if err else "failed"))
        try:
            return json.loads(done.stdout.decode("utf-8", "replace") or "null")
        except ValueError as e:
            raise ForgeError("gh %s: not JSON (%s)" % (" ".join(args[:3]), e))

    def pr(self, number):
        return self.call("pr", "view", str(number), "--json", GH_PR_FIELDS)

    def issue(self, number):
        """The issue, with `parent` and `subIssues` when this `gh` has them
        (2.94+): an older one is asked again without them."""
        try:
            return self.call("issue", "view", str(number), "--json", GH_ISSUE_FIELDS + ",parent,subIssues")
        except ForgeError as first:
            if "Unknown JSON field" not in str(first) and "unknown field" not in str(first).lower():
                raise
            return self.call("issue", "view", str(number), "--json", GH_ISSUE_FIELDS)

    def part_of(self, number):
        """Issues whose body has a `Part of #<number>` line."""
        found = self.call("issue", "list", "--state", "all", "--limit", "200", "--search",
                          '"Part of #%d" in:body' % number, "--json", GH_ISSUE_FIELDS)
        return [i for i in found or [] if pocock.PART_OF.search(i.get("body") or "")
                and int(pocock.PART_OF.search(i["body"]).group(1)) == number]


# --- git, read-only -------------------------------------------------------------

def _git(repo, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    done = subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          stdin=subprocess.DEVNULL, env=env)
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def blob(repo, sha, path):
    return _git(repo, "cat-file", "blob", "%s:%s" % (sha, path))


def commit_messages(repo, merge_base, head):
    return _git(repo, "log", "--no-merges", "--format=%B%x00", "%s..%s" % (merge_base, head)) or ""


def leaf(branch):
    """The branch's last component, lowercase, and the same without a
    trailing `-<hex>` suffix (as in `issue-39-review-setup-2b845c`)."""
    name = (branch or "").rsplit("/", 1)[-1].lower()
    bare = re.sub(r"-[0-9a-f]{4,}$", "", name)
    return {n for n in (name, bare) if len(n) >= 3}


def spec_files(repo, head, branch):
    """Markdown files under the spec roots of the head tree whose directory
    or file name is the branch's name, and whose shape is a spec's."""
    names = leaf(branch)
    if not names:
        return []
    listing = _git(repo, "ls-tree", "-r", "-z", "--name-only", head, "--", *SPEC_ROOTS) or ""
    out = []
    for path in sorted(p for p in listing.split("\0") if p.endswith(".md")):
        parts = path[:-3].lower().split("/")
        if not names.intersection(parts[1:]):
            continue
        if pocock.shape(blob(repo, head, path)) == "spec":
            out.append(path)
    return out


def escape(ref):
    return re.sub(r"[^\w.-]", "_", ref.strip("/"))


# --- The search -------------------------------------------------------------------

class Sources:
    """Collects the artifacts of one run and writes them into `root`."""

    def __init__(self, repo, root, target, pr=None, forge=None):
        self.repo, self.root, self.target, self.pr = repo, root, target, pr
        self.forge = forge or GitHub(repo)
        self.artifacts = []
        self.by_ref = {}
        self.notes = []
        base = target["base"]["sha"]
        text = blob(repo, base, pocock.TRACKER_DOC)
        self.tracker = dict(pocock.tracker_doc(text), path=pocock.TRACKER_DOC, sha=base)
        if text is not None:
            self.tracker["file"] = self.save("tracker-doc.md", text)

    def save(self, name, text):
        os.makedirs(os.path.join(self.root, SOURCES_DIR), exist_ok=True)
        rel = "%s/%s" % (SOURCES_DIR, name)
        with open(os.path.join(self.root, rel), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return rel

    def issue_reader(self):
        """Why issues can't be read through the tracker, or None."""
        t = self.tracker
        if t["status"] == "missing":
            return "no tracker doc at the base (%s)" % pocock.TRACKER_DOC
        if t["status"] == "drift":
            return "contract drift: tracker doc, %s" % t["detail"]
        if t["status"] == "unchecked":
            return "tracker doc: %s, not read in this version" % t["detail"]
        kind = (t["kind"] or "").lower()
        if kind == "github":
            return None if self.forge.available() else "GitHub tracker, but gh is not found on this machine"
        if kind == "local markdown":
            return "local markdown tracker: tickets are files, not `#N` references"
        return "%s tracker: not read in this version" % t["kind"]

    def add(self, ref, text, found_by, role=None, meta=None):
        """Record one artifact read; returns its entry."""
        if ref in self.by_ref:
            entry = self.by_ref[ref]
            if role and entry["role"] == "unknown" and "_text" in entry:
                # the relations tell what its shape could not
                entry.update(pocock.read_artifact(entry["_text"], role))
                entry["status"] = "drift" if entry["drift"] else "ok"
            return entry
        parsed = pocock.read_artifact(text, role)
        entry = {"ref": ref, "found_by": found_by}
        entry.update(meta or {})
        entry.update(parsed)
        entry["status"] = "drift" if entry["drift"] else "ok"
        name = ("issue-%s.md" % ref[1:]) if ref.startswith("#") else escape(ref)
        entry["file"] = self.save(name if name.endswith(".md") else name + ".md", text or "")
        entry["_text"] = text
        self.artifacts.append(entry)
        self.by_ref[ref] = entry
        return entry

    def unreadable(self, ref, found_by, why):
        if ref in self.by_ref:
            return self.by_ref[ref]
        entry = {"ref": ref, "found_by": found_by, "role": "unknown", "status": "unreadable",
                 "drift": [], "why": why}
        self.artifacts.append(entry)
        self.by_ref[ref] = entry
        return entry

    def read_issue(self, number, found_by, role=None):
        ref = "#%d" % number
        if ref in self.by_ref:
            return self.add(ref, None, found_by, role)
        try:
            data = self.forge.issue(number) or {}
        except ForgeError as e:
            return self.unreadable(ref, found_by, str(e))
        meta = {"title": data.get("title"), "url": data.get("url"), "state": data.get("state")}
        rel = {}
        if "parent" in data or "subIssues" in data:
            parent = data.get("parent") or {}
            rel = {"native": True, "parent": parent.get("number"),
                   "sub_issues": [s["number"] for s in (data.get("subIssues") or {}).get("nodes") or []
                                  if isinstance(s, dict) and s.get("number")]}
        else:
            rel = {"native": False}
        meta["relations"] = rel
        return self.add(ref, data.get("body") or "", found_by, role, meta)

    def read_file(self, path, found_by, role=None):
        text = blob(self.repo, self.target["head"]["sha"], path)
        if text is None:
            return self.unreadable(path, found_by, "no `%s` in the head tree" % path)
        return self.add(path, text, found_by, role)

    # --- relations

    def parent_of(self, ticket):
        rel = ticket.get("relations") or {}
        return rel.get("parent") or ticket.get("parent")

    def tickets_of(self, spec):
        """Read the spec's tickets: native sub-issues, else `Part of #` lines,
        else, for a local spec, the `issues/` files beside it."""
        if spec["ref"].startswith("#"):
            number = int(spec["ref"][1:])
            subs = (spec.get("relations") or {}).get("sub_issues") or []
            if subs:
                spec["tickets_by"] = "sub-issues"
                return [self.read_issue(n, "sub-issue of %s" % spec["ref"], "ticket") for n in subs]
            try:
                found = self.forge.part_of(number)
            except ForgeError as e:
                self.notes.append("tickets of %s not searched: %s" % (spec["ref"], e))
                return []
            spec["tickets_by"] = "`Part of %s` lines" % spec["ref"]
            out = []
            for i in found:
                meta = {"title": i.get("title"), "url": i.get("url"), "state": i.get("state"),
                        "relations": {"native": False, "parent": number}}
                out.append(self.add("#%d" % i["number"], i.get("body") or "",
                                    "`Part of %s` line" % spec["ref"], "ticket", meta))
            return out
        folder = os.path.dirname(spec["ref"])
        listing = _git(self.repo, "ls-tree", "-z", "--name-only", self.target["head"]["sha"] + ":" + folder + "/issues") \
            if folder else None
        names = sorted(n for n in (listing or "").split("\0") if n.endswith(".md"))
        if names:
            spec["tickets_by"] = "`%s/issues/` files" % folder
        return [self.read_file("%s/issues/%s" % (folder, n), "ticket file beside %s" % spec["ref"], "ticket")
                for n in names]

    # --- the order

    def find(self, spec_arg=None, no_spec=False):
        """Run the order; returns (found_by, refs read first)."""
        pr, target = self.pr, self.target
        if no_spec:
            return "the user said there is no spec", []
        if spec_arg:
            m = re.fullmatch(r"#?(\d+)", spec_arg.strip())
            return "named by the user", [int(m.group(1)) if m else spec_arg.strip()]
        # issue numbers name nothing in a local tracker: only files do
        numbered = (self.tracker.get("kind") or "").lower() != "local markdown"
        if numbered and pr:
            refs = pocock.closing_refs(pr.get("body") or "", pr.get("repo"))
            for n in pr.get("closing") or []:
                if n not in refs:
                    refs.append(n)
            if refs:
                return "closing references in the PR body", refs
        if numbered:
            refs = pocock.issue_refs(commit_messages(self.repo, target["merge_base"], target["head"]["sha"]))
            refs = [n for n in refs if not pr or n != pr.get("number")]
            if refs:
                return "issue references in commits", refs
        files = spec_files(self.repo, target["head"]["sha"], target.get("branch"))
        if len(files) == 1:
            return "spec file matching the branch", files
        if files:
            self.notes.append("several spec files match the branch: %s" % ", ".join(files))
        return None, []

    def gather(self, spec_arg=None, no_spec=False):
        found_by, refs = self.find(spec_arg, no_spec)
        reader = self.issue_reader()
        first = []
        for ref in refs:
            if isinstance(ref, int):
                if reader:
                    first.append(self.unreadable("#%d" % ref, found_by, reader))
                else:
                    first.append(self.read_issue(ref, found_by))
            else:
                first.append(self.read_file(ref, found_by))
        # the spec: one read first, else the parent of a ticket read first
        spec = next((a for a in first if a["role"] == "spec"), None)
        if spec is None:
            parents = [self.parent_of(a) for a in first if a["role"] == "ticket" and self.parent_of(a)]
            if parents and not reader:
                spec = self.read_issue(parents[0], "parent of %s" % next(
                    a["ref"] for a in first if self.parent_of(a) == parents[0]), "spec")
        tickets = []
        if spec is not None and spec["status"] != "unreadable":
            tickets = self.tickets_of(spec)
        named = [a for a in first if a["role"] == "ticket"]
        whole = spec is not None and (spec in first or not named)
        for a in self.artifacts:
            if a["role"] == "ticket":
                a["scope"] = "in scope" if (a in named or whole) else "sibling"
            elif a["role"] == "spec":
                a["scope"] = "spec"
            else:
                a["scope"] = "in scope" if a in first else "sibling"
        return self.summary(found_by, spec, first, reader)

    def summary(self, found_by, spec, first, reader):
        pr_entry = None
        if self.pr is not None:
            body = self.pr.get("body") or ""
            pr_entry = dict(pocock.read_pr_body(body), number=self.pr.get("number"), url=self.pr.get("url"),
                            file=self.save("pr-%s.md" % self.pr.get("number"), body))
        intent, ask = self.intent(found_by, spec, first, reader)
        declared = "no PR body read"
        if pr_entry is not None:
            declared = pr_entry["status"] if pr_entry["status"] != "drift" else \
                "not-evaluable (contract drift: PR #%s body, %s)" % (pr_entry["number"], "; ".join(pr_entry["drift"]))
        for a in self.artifacts:
            a.pop("_text", None)
        return {
            "contract": pocock.UPSTREAM,
            "found_by": found_by,
            "tracker": self.tracker,
            "pr": pr_entry,
            "spec": spec["ref"] if spec else None,
            "artifacts": self.artifacts,
            "dimensions": {"intent": intent, "declared": declared},
            "notes": self.notes,
            "ask": ask,
        }

    def intent(self, found_by, spec, first, reader):
        """(intent dimension, question for the user or None)."""
        if found_by == "the user said there is no spec":
            return "not-evaluable (no spec: the user said there is none)", None
        if found_by is None:
            many = [n for n in self.notes if n.startswith("several spec files")]
            return ("not-evaluable (no spec found)",
                    "no spec found%s: ask the user where it is (an issue `#N`, a path in the repository, or none)"
                    % (" (%s)" % many[0] if many else ""))
        if not self.artifacts:
            return "not-evaluable (no spec found)", None
        lost = [a for a in self.artifacts if a["status"] == "unreadable" and a.get("scope") != "sibling"]
        if lost and len(lost) == len([a for a in self.artifacts if a.get("scope") != "sibling"]):
            return "not-evaluable (%s)" % (reader or "; ".join("%s: %s" % (a["ref"], a["why"]) for a in lost)), None
        drifted = [a for a in self.artifacts if a["status"] == "drift" and a.get("scope") != "sibling"]
        if drifted:
            return "not-evaluable (contract drift: %s)" % "; ".join(
                "%s %s, %s" % (a["role"], a["ref"], ", ".join(a["drift"])) for a in drifted), None
        if lost and found_by != "issue references in commits":
            # a commit's `#N` may name a pull request: only a reference the
            # PR closes, or one the user named, must be readable
            return "not-evaluable (%s)" % "; ".join("%s: %s" % (a["ref"], a["why"]) for a in lost), None
        return EVALUABLE, None


def gather(repo, root, target, pr=None, spec_arg=None, no_spec=False, forge=None):
    """Find, read and check the run's sources; writes `sources/` and
    `sources.json` under `root` and returns what it wrote in `sources.json`."""
    found = Sources(repo, root, target, pr, forge).gather(spec_arg, no_spec)
    with open(os.path.join(root, SOURCES), "w", encoding="utf-8") as fh:
        json.dump(found, fh, indent=2)
        fh.write("\n")
    return found
