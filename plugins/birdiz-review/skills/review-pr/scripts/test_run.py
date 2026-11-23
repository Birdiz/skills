"""Tests for a review run, files in and files out: python3 -I -m unittest discover -s <this directory>

Each test builds a tiny git repository, runs run.py on it as the skill does
(`python3 -I`, another working directory, the state directory in a
temporary folder), then reads the run directory and checks it with
validate.py and check-pointers.py.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import validate  # noqa: E402

GIT = shutil.which("git")

BLOCKING = """### F-BRK-001 Public method renamed

```yaml
id: F-BRK-001
axis: contracts
status: unverified
severity: high
confidence: high
sensitive: false
promptable: true
locations:
  - src/app.py:1
diff: {diff}
attention: must-read
blocks_merge: true
fan_in: 3
```

**Evidence.** `src/app.py:1` "def greet(name, punctuation):" takes a new required argument.

**Reviewer question.** Do the three callers outside the diff pass it?
"""


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE="2026-11-01T00:00:00Z", GIT_COMMITTER_DATE="2026-11-01T00:00:00Z")
    subprocess.run([GIT, "-C", repo] + list(args), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out = subprocess.run([GIT, "-C", repo, "rev-parse", "--verify", "--quiet", "HEAD"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return out.stdout.strip()


def write(repo, rel, text):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def snapshot(top):
    """Every file and directory under `top`, with its content hash and mtime."""
    out = {}
    for d, dirs, files in os.walk(top):
        for name in dirs + files:
            path = os.path.join(d, name)
            st = os.lstat(path)
            digest = ""
            if os.path.isfile(path) and not os.path.islink(path):
                with open(path, "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
            out[os.path.relpath(path, top)] = (digest, st.st_mtime_ns)
    return out


class Fixture:
    """A repository with `main` and a branch `feature/x` that modifies,
    adds in a new directory, renames and deletes a file."""

    def __init__(self, test):
        self.tmp = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.tmp)
        self.repo = os.path.join(self.tmp, "shop")
        self.state = os.path.join(self.tmp, "state")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.repo)
        os.makedirs(self.bin)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        write(self.repo, "src/app.py", "def greet(name):\n    return 'hello ' + name\n")
        write(self.repo, "README.md", "# Shop\n")
        write(self.repo, "old.txt", "to be deleted\n")
        git(self.repo, "add", "-A")
        self.base = git(self.repo, "commit", "-qm", "base")
        git(self.repo, "checkout", "-qb", "feature/x")
        write(self.repo, "src/app.py", "def greet(name, punctuation):\n    return 'hello ' + name + punctuation\n")
        write(self.repo, "lib/billing/invoice.py", "TOTAL = 1\n")
        git(self.repo, "mv", "README.md", "README.txt")
        git(self.repo, "rm", "-q", "old.txt")
        git(self.repo, "add", "-A")
        self.head = git(self.repo, "commit", "-qm", "head")
        git(self.repo, "checkout", "-q", "main")

    def commit_on_branch(self, rel, text, branch="feature/x"):
        """A new head on the branch, written in a scratch worktree so the
        fixture's own working copy stays on `main`."""
        wt = os.path.join(self.tmp, "wt")
        git(self.repo, "worktree", "add", "-q", wt, branch)
        write(wt, rel, text)
        git(wt, "add", "-A")
        sha = git(wt, "commit", "-qm", "more")
        git(self.repo, "worktree", "remove", "--force", wt)
        return sha

    def tool(self, name, output):
        path = os.path.join(self.bin, name)
        write(self.bin, name, "#!/bin/sh\necho '%s'\n" % output)
        os.chmod(path, 0o755)

    def run(self, *args, cwd=None):
        env = dict(os.environ, XDG_STATE_HOME=self.state,
                   PATH=os.pathsep.join([self.bin, os.path.dirname(GIT), "/usr/bin", "/bin"]))
        done = subprocess.run([sys.executable, "-I", os.path.join(HERE, "run.py")] + list(args) + ["--repo", self.repo],
                              cwd=cwd or self.tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
        lines = done.stdout.strip().split("\n")
        root = lines[-1][len("RUN: "):] if lines and lines[-1].startswith("RUN: ") else None
        return done.returncode, root, done.stdout + done.stderr


def check(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = validate.main(["validate.py"] + list(args))
    return code, out.getvalue()


def entry(name, *args):
    done = subprocess.run([sys.executable, "-I", os.path.join(HERE, name)] + list(args),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return done.returncode, done.stdout + done.stderr


@unittest.skipIf(GIT is None, "git is not installed")
class TestRun(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(self)

    def test_the_run_directory_passes_the_review_validator(self):
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        code, report = check(root, "--require", "brief")
        self.assertEqual(code, 0, report)
        self.assertIn("RESULT: OK", report)
        self.assertIn("errors 0, warnings 0", report)
        code, report = entry("check-pointers.py", root)
        self.assertEqual(code, 0, report)

    def test_the_run_directory_is_keyed_by_repo_branch_and_head_short_sha(self):
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        expected = os.path.join(self.fx.state, "birdiz-review", "runs", "shop", "feature%2Fx", self.fx.head[:12])
        self.assertEqual(os.path.realpath(root), os.path.realpath(expected))
        os.environ["XDG_STATE_HOME"], saved = self.fx.state, os.environ.get("XDG_STATE_HOME")
        try:
            import review_run
            self.assertEqual(review_run.branch_runs(self.fx.repo, "feature/x"), os.path.dirname(expected))
        finally:
            os.environ.pop("XDG_STATE_HOME") if saved is None else os.environ.__setitem__("XDG_STATE_HOME", saved)
        header = json.loads(read(os.path.join(root, "run.json")))
        self.assertEqual(header["head"]["sha"], self.fx.head)
        self.assertEqual(header["base"]["sha"], self.fx.base)
        self.assertEqual(header["diff"], "%s..%s" % (self.fx.base[:12], self.fx.head[:12]))

    def test_a_range_is_accepted_and_keyed_by_its_head_branch(self):
        code, root, out = self.fx.run("main..feature/x")
        self.assertEqual(code, 0, out)
        self.assertEqual(os.path.basename(os.path.dirname(root)), "feature%2Fx")
        code, root, out = self.fx.run("%s...%s" % (self.fx.base, self.fx.head))
        self.assertEqual(code, 0, out)
        self.assertEqual(os.path.basename(root), self.fx.head[:12])

    def test_an_empty_diff_is_refused_and_nothing_is_written(self):
        for target in ("main", "main..main", "feature/x..main"):
            with self.subTest(target=target):
                code, root, out = self.fx.run(target)
                self.assertEqual(code, 2, out)
                self.assertIn("empty diff", out)
                self.assertIsNone(root)
        self.assertFalse(os.path.exists(self.fx.state))

    def test_an_unknown_ref_is_refused(self):
        for target in ("nope", "main..nope", "--all", "main.."):
            with self.subTest(target=target):
                code, root, out = self.fx.run(target)
                self.assertNotEqual(code, 0, out)
                self.assertIsNone(root)
        self.assertFalse(os.path.exists(self.fx.state))

    def test_nothing_is_written_to_the_repository_or_its_working_copy(self):
        write(self.fx.repo, "src/app.py", "uncommitted change on main\n")
        write(self.fx.repo, "untracked.txt", "left alone\n")
        before = snapshot(self.fx.repo)
        code, root, out = self.fx.run("feature/x", cwd=self.fx.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual(snapshot(self.fx.repo), before)
        self.assertFalse(os.path.realpath(root).startswith(os.path.realpath(self.fx.repo) + os.sep))
        # The head tree is read from git objects, not from the working copy.
        tree = os.path.join(root, "repo-" + self.fx.head[:12])
        self.assertIn("punctuation", read(os.path.join(tree, "src", "app.py")))
        self.assertFalse(os.path.exists(os.path.join(tree, "untracked.txt")))

    def test_a_run_root_inside_the_repository_is_refused(self):
        self.fx.state = os.path.join(self.fx.repo, ".state")
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 2, out)
        self.assertIn("inside the reviewed repository", out)
        self.assertFalse(os.path.exists(self.fx.state))

    def test_the_header_records_the_detector_tools_found_with_versions(self):
        self.fx.tool("squawk", "squawk 1.4.2")
        self.fx.tool("oasdiff", "oasdiff version v1.10.3")
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        tools = {t["name"]: t for t in json.loads(read(os.path.join(root, "run.json")))["tools"]}
        self.assertEqual((tools["squawk"]["found"], tools["squawk"]["version"]), (True, "1.4.2"))
        self.assertEqual(tools["oasdiff"]["version"], "1.10.3")
        self.assertTrue(tools["git"]["found"])
        self.assertRegex(tools["git"]["version"], r"^\d+\.\d+")
        self.assertFalse(tools["griffe"]["found"])
        self.assertNotIn("version", tools["griffe"])
        brief = read(os.path.join(root, "brief.md"))
        self.assertIn("squawk 1.4.2", brief)
        self.assertIn("not found: roave-backward-compatibility-check", brief)

    def test_git_signals_and_one_bucket_per_changed_file(self):
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        signals = json.loads(read(os.path.join(root, "signals", "git-changes.json")))
        changes = {f["path"]: f["change"] for f in signals["files"]}
        self.assertEqual(changes, {"src/app.py": "modified", "lib/billing/invoice.py": "added",
                                   "README.txt": "renamed", "old.txt": "deleted"})
        self.assertEqual(signals["new_directories"], ["lib", "lib/billing"])
        self.assertFalse(signals["content"])
        reasons = {s["path"]: s["reason"] for s in signals["signals"]}
        self.assertEqual(reasons["lib/billing/invoice.py"], "added in a new directory `lib/`")
        self.assertNotIn("src/app.py", reasons)
        brief = read(os.path.join(root, "brief.md"))
        unproven = brief.split("## Unproven")[1].split("## ")[0]
        for path in changes:
            self.assertEqual(brief.count("- `%s`" % path), 1, path)
            self.assertIn("- `%s`: no content detector reads this file type" % path, unproven)
        self.assertIn("## Skim\n\nNone.", brief)

    def test_the_brief_states_the_dimensions_not_run(self):
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        brief = read(os.path.join(root, "brief.md"))
        gaps = brief.split("## Coverage gaps")[1].split("## Verdict")[0]
        for line in ("- intent (`INT`): not run", "- contracts (`BRK`): not run", "- structure (`STR`): not run",
                     "- gates, test integrity, adversarial: not in this version."):
            self.assertIn(line, gaps)
        self.assertIn("Proposed verdict: merge, round 1 (intent not checked: step not in this version;"
                      " contracts, structure, gates, test integrity, adversarial not run).", brief)

    def test_the_round_counts_distinct_heads_of_the_same_branch(self):
        def verdict(root):
            return next(l for l in read(os.path.join(root, "brief.md")).split("\n") if l.startswith("Proposed verdict:"))

        code, first, out = self.fx.run("feature/x")
        self.assertIn(", round 1 ", verdict(first))
        code, again, out = self.fx.run("feature/x")
        self.assertEqual(again, first)
        self.assertIn(", round 1 ", verdict(again), "the same head is not a new round")
        self.fx.commit_on_branch("src/app.py", "def greet(name, punctuation='!'):\n    return name\n")
        code, second, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        self.assertNotEqual(second, first)
        self.assertIn(", round 2 ", verdict(second))
        git(self.fx.repo, "branch", "other", "feature/x")
        code, other, out = self.fx.run("other")
        self.assertIn(", round 1 ", verdict(other), "another branch counts its own rounds")
        self.assertEqual(check(second, "--require", "brief")[0], 0)

    def test_a_merge_blocking_finding_makes_the_brief_stale_then_a_fix(self):
        code, root, out = self.fx.run("feature/x")
        header = json.loads(read(os.path.join(root, "run.json")))
        path = os.path.join(root, "findings", "contracts.md")
        text = read(path).replace("## Findings\n\nNone.\n", "## Findings\n\n" + BLOCKING.format(diff=header["diff"]))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        code, report = check(root, "--require", "brief")
        self.assertEqual(code, 1, report)
        self.assertIn("run brief.py", report)
        code, out = entry("brief.py", root)
        self.assertEqual(code, 0, out)
        self.assertIn("Proposed verdict: fix, round 1", out)
        code, report = check(root, "--require", "brief")
        self.assertEqual(code, 0, report)
        brief = read(os.path.join(root, "brief.md"))
        must = brief.split("## Must read")[1].split("## ")[0]
        self.assertIn("- `src/app.py`\n  - F-BRK-001 `src/app.py:1`: Public method renamed."
                      " **Question:** Do the three callers outside the diff pass it?", must)
        self.assertNotIn("`src/app.py`", brief.split("## Unproven")[1].split("## ")[0])
        self.assertEqual(entry("check-pointers.py", root)[0], 0)

    def test_a_third_head_with_a_merge_blocking_finding_proposes_close_and_reprompt(self):
        self.fx.run("feature/x")
        self.fx.commit_on_branch("a.txt", "2\n")
        self.fx.run("feature/x")
        self.fx.commit_on_branch("a.txt", "3\n")
        code, root, out = self.fx.run("feature/x")
        self.assertIn("Proposed verdict: merge, round 3", out)
        header = json.loads(read(os.path.join(root, "run.json")))
        path = os.path.join(root, "findings", "contracts.md")
        text = read(path).replace("## Findings\n\nNone.\n", "## Findings\n\n" + BLOCKING.format(diff=header["diff"]))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out = entry("brief.py", root)
        self.assertIn("Proposed verdict: close-and-reprompt, round 3", out)
        self.assertEqual(check(root, "--require", "brief")[0], 0)


if __name__ == "__main__":
    unittest.main()
