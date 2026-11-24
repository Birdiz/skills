"""Tests for eval_review.py: python3 -I -m unittest discover -s <this directory>

Each test writes a tiny synthetic corpus in a temporary directory: a git
repository with one change, and case files labelling its must-read items.
The judgment steps are played by a fake agent, a script that fills the
worksheets as a step would, so no model runs.
"""
import contextlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("eval_review", os.path.join(HERE, "eval_review.py"))
eval_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_review)

GIT = shutil.which("git")

MIGRATION = "db/migrations/002_drop_email.sql"

# The contracts step as a fake agent: judges the drop one-way and the new
# required parameter breaking, each with a must-read finding, and adds a
# must-read finding on the README no detector signalled. The structure step
# judges nothing new. Called as: fake_agent.py <axis> <run directory>.
FAKE_AGENT = r'''
import json, os, sys

axis, run = sys.argv[1], sys.argv[2]
diff = json.load(open(os.path.join(run, "run.json")))["diff"]
path = os.path.join(run, "findings", axis + ".md")
text = open(path, encoding="utf-8").read()


def finding(n, location, evidence, title):
    return """### F-BRK-%03d %s

```yaml
id: F-BRK-%03d
axis: contracts
status: unverified
severity: high
confidence: high
sensitive: false
promptable: true
locations:
  - %s
diff: %s
attention: must-read
blocks_merge: true
fan_in: unknown
```

**Evidence.** %s

**Reviewer question.** Is this wanted?
""" % (n, title, n, location, diff, evidence)


out, section = [], None
for line in text.split("\n"):
    if line.startswith("## "):
        section = line[3:]
    if section == "Coverage" and "| not-evaluable | Step not run yet" in line:
        line = "| %s | evaluated | |" % line.split("|")[1].strip()
    elif line.startswith("Axis: "):
        line = "Axis: evaluated"
    elif section == "Signals" and line.endswith("| ? | |"):
        cell = "one-way | F-BRK-001" if "migrations `drop`" in line else "breaking | F-BRK-002"
        line = line[:line.rindex("| ? | |")] + "| %s |" % cell
    elif section == "Declared" and line.endswith("| ? | |"):
        line = line[:line.rindex("| ? | |")] + "| one-way | |"
    out.append(line)
text = "\n".join(out)
if axis == "contracts":
    found = [
        finding(1, "db/migrations/002_drop_email.sql:1",
                '`db/migrations/002_drop_email.sql:1` "ALTER TABLE users DROP COLUMN email;" drops a column.',
                "Migration drops the email column"),
        finding(2, "src/app.py:1",
                '`src/app.py:1` "def greet(name, punctuation):" adds a required parameter.',
                "Public function takes a new required parameter"),
        finding(3, "README.md:3", '`README.md:3` "More." changes the readme.', "Readme changed"),
    ]
    text = text.replace("## Findings\n\nNone.\n", "## Findings\n\n" + "\n".join(found))
open(path, "w", encoding="utf-8").write(text)
'''


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE="2026-11-01T00:00:00Z", GIT_COMMITTER_DATE="2026-11-01T00:00:00Z")
    subprocess.run([GIT, "-C", repo] + list(args), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out = subprocess.run([GIT, "-C", repo, "rev-parse", "--verify", "--quiet", "HEAD"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, universal_newlines=True)
    return out.stdout.strip()


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Corpus:
    """A corpus directory beside a repository `shop` whose change drops a
    column (glance by its detector), adds a required parameter (glance),
    edits the README (unproven: no content detector reads it) and only adds
    a test to a test file (skim)."""

    def __init__(self, test):
        self.tmp = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.tmp)
        self.repo = os.path.join(self.tmp, "shop")
        self.dir = os.path.join(self.tmp, "corpus")
        os.makedirs(self.repo)
        os.makedirs(self.dir)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        write(self.repo, "src/app.py", 'def greet(name):\n    return "hello " + name\n')
        write(self.repo, "db/migrations/001_users.sql", "CREATE TABLE users (id INT, email TEXT);\n")
        write(self.repo, "tests/test_app.py",
              'from src.app import greet\n\n\ndef test_greet():\n    assert greet("a", "") == "hello a"\n')
        write(self.repo, "README.md", "# Shop\n")
        git(self.repo, "add", "-A")
        self.base = git(self.repo, "commit", "-qm", "base")
        write(self.repo, "src/app.py", 'def greet(name, punctuation):\n    return "hello " + name + punctuation\n')
        write(self.repo, MIGRATION, "ALTER TABLE users DROP COLUMN email;\n")
        with open(os.path.join(self.repo, "tests/test_app.py"), "a", encoding="utf-8") as fh:
            fh.write('\n\ndef test_greet_again():\n    assert greet("b", "!") == "hello b!"\n')
        write(self.repo, "README.md", "# Shop\n\nMore.\n")
        git(self.repo, "add", "-A")
        self.head = git(self.repo, "commit", "-qm", "head")
        write(self.tmp, "bin/fake_agent.py", FAKE_AGENT)
        self.agent = "%s -I %s {axis} {run}" % (shlex.quote(sys.executable),
                                                shlex.quote(os.path.join(self.tmp, "bin", "fake_agent.py")))

    def case(self, name, **labels):
        data = {"repo": "../shop", "target": "%s..%s" % (self.base, self.head), "no_spec": True}
        data.update(labels)
        write(self.dir, name + ".json", json.dumps(data))

    def out(self, name="out"):
        return os.path.join(self.tmp, name)

    def run(self, *args, agent=None, out="out"):
        return main("run", self.dir, "--out", self.out(out), "--agent", agent or self.agent, *args)

    def report(self, out="out"):
        with open(os.path.join(self.out(out), "report.json"), encoding="utf-8") as fh:
            return json.load(fh)


def main(*args):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = eval_review.main(["eval_review.py"] + list(args))
    return code, stdout.getvalue() + stderr.getvalue()


@unittest.skipIf(GIT is None, "git is not installed")
class TestEvalReview(unittest.TestCase):

    def setUp(self):
        self.c = Corpus(self)

    def items(self, case=0, out="out"):
        return {i["path"]: i["bucket"] for i in self.c.report(out)["cases"][case]["items"]}

    def test_the_steps_mark_the_items_must_read_and_the_noise_is_counted(self):
        self.c.case("shop", must_read=[MIGRATION], unnecessary=["src/app.py"])
        code, out = self.c.run()
        self.assertEqual(code, 0, out)
        case = self.c.report()["cases"][0]
        self.assertEqual(case["failures"], [])
        self.assertEqual(self.items(), {MIGRATION: "must-read"})
        self.assertEqual(case["noise"], ["src/app.py"])
        self.assertEqual(case["unlabelled"], ["README.md"])
        self.assertTrue(case["verdict"].startswith("Proposed verdict: fix, round 1"), case["verdict"])
        totals = self.c.report()["totals"]
        self.assertEqual((totals["recalled"], totals["items"], totals["recall"]), (1, 1, 1.0))
        self.assertEqual((totals["noise"], totals["must_read_files"], totals["unlabelled"]), (1, 3, 1))
        self.assertIn("recall: 1/1 must-read items (100.0%)", out)
        self.assertIn("unlabelled must-read files (label them): `README.md`", out)
        self.assertIn("PASS: 0 of 1 case(s) failed", out)

    def test_a_must_read_item_classified_skim_fails(self):
        self.c.case("shop", must_read=[MIGRATION, {"path": "tests/test_app.py", "why": "pins greet"}])
        code, out = self.c.run(agent="none")
        self.assertEqual(code, 1, out)
        self.assertEqual(self.items(), {MIGRATION: "glance", "tests/test_app.py": "skim"})
        case = self.c.report()["cases"][0]
        self.assertEqual(case["failures"], ["must-read item `tests/test_app.py` classified skim"])
        self.assertEqual(self.c.report()["totals"]["skim"], 1)
        self.assertIn("FAIL   `tests/test_app.py`: skim (pins greet)", out)
        self.assertIn("missed `%s`: glance" % MIGRATION, out)
        self.assertIn("recall: 0/2 must-read items (0.0%)", out)

    def test_score_reads_the_labels_again_without_replaying(self):
        self.c.case("shop", must_read=[MIGRATION], unnecessary=["src/app.py"])
        self.c.run()
        shutil.rmtree(self.c.repo)  # nothing is replayed
        self.c.case("shop", must_read=[MIGRATION, "README.md"], unnecessary=["src/app.py"])
        code, out = main("score", self.c.dir, self.c.out())
        self.assertEqual(code, 0, out)
        case = self.c.report()["cases"][0]
        self.assertEqual(case["unlabelled"], [])
        self.assertEqual(self.items(), {MIGRATION: "must-read", "README.md": "must-read"})

    def test_compare_lists_the_items_lost_since_an_earlier_report(self):
        self.c.case("shop", must_read=[MIGRATION])
        self.c.run(out="before")
        before = os.path.join(self.c.out("before"), "report.json")
        code, out = self.c.run("--compare", before, agent="none", out="after")
        self.assertEqual(code, 0, out)
        cmp_ = self.c.report("after")["compare"]
        self.assertEqual(cmp_["lost"], [{"case": "shop", "path": MIGRATION, "now": "glance"}])
        self.assertEqual(cmp_["gained"], [])
        self.assertIn("lost   shop `%s`: now glance" % MIGRATION, out)

    def test_a_case_without_a_spec_says_intent_was_not_checked(self):
        self.c.case("shop", must_read=[MIGRATION])
        data = json.load(open(os.path.join(self.c.dir, "shop.json")))
        del data["no_spec"]
        write(self.c.dir, "shop.json", json.dumps(data))
        code, out = self.c.run(agent="none")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.c.report()["cases"][0]["ask"])
        self.assertIn("intent not checked, run.py asked:", out)

    def test_a_label_outside_the_diff_is_missed(self):
        self.c.case("shop", must_read=["src/gone.py"])
        code, out = self.c.run(agent="none")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.items(), {"src/gone.py": "not in the diff"})

    def test_a_refused_run_or_a_failed_step_fails_the_case(self):
        self.c.case("empty", target="%s..%s" % (self.c.base, self.c.base), must_read=[MIGRATION])
        self.c.case("shop", must_read=[MIGRATION])
        code, out = self.c.run(agent="%s -c 'raise SystemExit(3)'" % shlex.quote(sys.executable))
        self.assertEqual(code, 1, out)
        empty, shop = self.c.report()["cases"]
        self.assertTrue(empty["failures"][0].startswith("run.py exit 2"), empty["failures"])
        self.assertEqual(empty["items"][0]["bucket"], "no brief")
        self.assertEqual(shop["failures"], ["step contracts exit 3", "step structure exit 3"])
        self.assertIn("FAIL: 2 of 2 case(s) failed", out)

    def test_the_case_option_replays_only_the_named_cases(self):
        self.c.case("one", must_read=[MIGRATION])
        self.c.case("two", must_read=[MIGRATION])
        code, out = self.c.run("--case", "two", agent="none")
        self.assertEqual([c["name"] for c in self.c.report()["cases"]], ["two"])

    def test_a_malformed_corpus_is_refused_before_any_run(self):
        for labels, message in (
                ({"must_raed": []}, "unknown keys must_raed"),
                ({"pr": 3}, "give one of `target`"),
                ({"must_read": ["a.py"], "unnecessary": ["a.py"]}, "labelled twice: a.py"),
                ({"spec": "#3"}, "excludes `no_spec`")):
            self.c.case("shop", **labels)
            code, out = self.c.run(agent="none")
            self.assertEqual(code, 2, out)
            self.assertIn(message, out)
            self.assertFalse(os.path.exists(os.path.join(self.c.out(), "runs.json")))

    def test_neither_the_corpus_nor_the_output_may_sit_in_this_repository(self):
        self.c.case("shop", must_read=[MIGRATION])
        code, out = main("run", HERE, "--agent", "none")
        self.assertEqual(code, 2)
        self.assertIn("keep it outside this public repository", out)
        code, out = main("run", self.c.dir, "--out", os.path.join(HERE, "eval-out"), "--agent", "none")
        self.assertEqual(code, 2)
        self.assertIn("keep them outside", out)
        self.assertFalse(os.path.exists(os.path.join(HERE, "eval-out")))


if __name__ == "__main__":
    unittest.main()
