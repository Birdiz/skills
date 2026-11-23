"""Tests for detect.py and write.py: python3 -I -m unittest discover -s <this directory>

Each test builds a tiny git repository, runs an entry point's main(), and
checks the files and the report.
"""
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import detect  # noqa: E402
import write  # noqa: E402

AGENTS = """# Agents

Intro kept as is.

## Agent skills

### Issue tracker

Issues live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context. See `docs/agents/domain.md`.

## Other section

Untouched.
"""

TRACKER = """# Issue tracker: GitHub

## Conventions

- **Read an issue**: `gh issue view <number>`.

## When a skill says "fetch the relevant ticket"

Read it.
"""

DOMAIN = """# Domain Docs

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root
- **`docs/adr/`**: read ADRs.
"""

FILES = {
    "AGENTS.md": AGENTS,
    "docs/agents/issue-tracker.md": TRACKER,
    "docs/agents/domain.md": DOMAIN,
    "GLOSSARY.md": "# Glossary\n",
    "docs/adr/0001-x.md": "# x\n",
    "composer.json": "{}\n",
    "src/Kernel.php": "<?php\n",
    "src/Security/LoginVoter.php": "<?php\nclass LoginVoter {}\n",
    "src/Security/Hasher.php": "<?php\n$h = password_hash($p, PASSWORD_DEFAULT);\n",
    "src/Billing/Charge.php": "<?php\nuse Stripe\\Charge;\n\\Stripe\\Charge::create([]);\n",
    "src/Service/Notifier.php": "<?php\n\n$c = new \\Stripe\\StripeClient();\n",
    "migrations/Version1.php": "<?php\n$this->addSql('DROP TABLE legacy');\n",
    "src/Controller/HomeController.php": "<?php\n#[Route('/')]\n",
    "tests/Security/LoginTest.php": "<?php\n",
    "src/Billing/RefundTest.php": "<?php\n$this->addSql('DROP TABLE x');\n",
    "lib/test_pay.py": "import stripe\n",
    "web/pay.spec.ts": "import Stripe from 'stripe';\n",
}


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false"] + list(args), check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True).stdout


def run(module, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = module.main([module.__name__ + ".py"] + list(args))
    return code, out.getvalue()


def snapshot(repo):
    out = {}
    for d, dirs, files in os.walk(repo):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, repo)] = fh.read()
    return out


class Base(unittest.TestCase):
    files = FILES

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = os.path.join(self.tmp, "shop")
        os.makedirs(self.repo)
        for rel, text in self.files.items():
            p = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")
        self.state = os.path.join(self.tmp, "state")
        self.env = dict(os.environ, XDG_STATE_HOME=self.state)
        patcher = unittest.mock.patch.dict(os.environ, {"XDG_STATE_HOME": self.state})
        patcher.start()
        self.addCleanup(patcher.stop)

    def detect(self, *extra):
        code, out = run(detect, self.repo, "--json", "--no-gh", *extra)
        self.assertEqual(code, 0)
        return json.loads(out)

    def read(self, rel):
        with open(os.path.join(self.repo, rel), encoding="utf-8", newline="") as fh:
            return fh.read()


import unittest.mock  # noqa: E402


class TestDetect(Base):
    def test_detect_writes_nothing(self):
        before = snapshot(self.repo)
        run(detect, self.repo, "--no-gh")
        run(detect, self.repo, "--json", "--no-gh")
        self.assertEqual(snapshot(self.repo), before)
        self.assertFalse(os.path.exists(self.state))

    def test_stacks_come_with_a_pointer(self):
        r = self.detect()
        stacks = {s["name"]: s["pointer"] for s in r["stacks"]}
        self.assertEqual(stacks["php"], "composer.json")
        self.assertEqual(stacks["python"], "1 .py file(s), e.g. lib/test_pay.py")
        self.assertEqual(sorted(stacks), ["php", "python", "typescript"])

    def test_each_proposed_zone_has_a_pointer_to_what_suggested_it(self):
        props = {(p["zone"], p["glob"]): p for p in self.detect()["proposals"]}
        self.assertEqual(props[("auth", "src/Security/**")]["pointer"], "src/Security/ (2 file(s))")
        self.assertEqual(props[("payments", "src/Billing/**")]["why"], "directory name")
        self.assertEqual(props[("payments", "src/Service/Notifier.php")]["pointer"],
                         'src/Service/Notifier.php:3 "$c = new \\Stripe\\StripeClient();"')
        self.assertIn(("irreversible", "migrations/**"), props)
        self.assertIn(("public-api", "src/Controller/**"), props)
        # a content hit inside a proposed directory of the same zone is not repeated
        self.assertNotIn(("auth", "src/Security/Hasher.php"), props)
        self.assertNotIn(("payments", "src/Billing/Charge.php"), props)
        # tests are not proposed, in a test directory or by their file name
        self.assertFalse(any(g and (g.startswith("tests/") or "Test." in g or "test_" in g or ".spec." in g)
                             for _, g in props), sorted(props))
        for p in props.values():
            self.assertTrue(p["pointer"])

    def test_tools_are_reported_with_where_they_were_found(self):
        tools = {t["name"]: t for t in self.detect()["tools"]}
        self.assertTrue(tools["git"]["found"])
        self.assertIn("roave-backward-compatibility-check", tools)
        os.makedirs(os.path.join(self.repo, "vendor", "bin"))
        open(os.path.join(self.repo, "vendor", "bin", "deptrac"), "w").close()
        with unittest.mock.patch.dict(os.environ, {"PATH": os.path.dirname(shutil.which("git"))}):
            tools = {t["name"]: t for t in self.detect()["tools"]}
        self.assertEqual(tools["deptrac"]["where"], "vendor/bin/deptrac")

    def test_pocock_artifacts_in_the_expected_shape_are_ok(self):
        status = {p["artifact"]: p["status"] for p in self.detect()["pocock"]}
        self.assertEqual(status, {"agent skills block": "ok", "tracker doc": "ok", "domain doc": "ok",
                                  "glossary": "ok", "ADRs": "ok"})

    def test_the_current_review_md_is_read_back(self):
        self.assertIsNone(self.detect()["current"])
        run(write, self.repo, "--stack", "php", "--zone", "src/Security/**", "auth", "--no-gh")
        cur = self.detect()["current"]
        self.assertEqual(cur["stacks"], ["php"])
        self.assertEqual(cur["risk_map"][0]["glob"], "src/Security/**")
        self.assertEqual(cur["problems"], [])

    def test_text_report_names_every_part(self):
        code, out = run(detect, self.repo, "--no-gh")
        self.assertEqual(code, 0)
        for part in ("Write guard", "Stacks", "not stored", "Pocock artifacts", "Proposed risk zones",
                     "auth `src/Security/**` (directory name"):
            self.assertIn(part, out)


class TestPocockShape(Base):
    def status(self):
        return {p["artifact"]: (p["status"], p["detail"]) for p in self.detect()["pocock"]}

    def put(self, rel, text):
        with open(os.path.join(self.repo, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_missing_docs_are_named(self):
        os.remove(os.path.join(self.repo, "docs/agents/issue-tracker.md"))
        os.remove(os.path.join(self.repo, "docs/agents/domain.md"))
        self.put("AGENTS.md", "# Agents\n")
        s = self.status()
        self.assertEqual(s["tracker doc"][0], "missing")
        self.assertEqual(s["domain doc"][0], "missing")
        self.assertEqual(s["agent skills block"][0], "missing")
        self.assertIn("setup-matt-pocock-skills", s["agent skills block"][1])

    def test_a_tracker_without_the_fetch_section_drifts(self):
        self.put("docs/agents/issue-tracker.md", "# Issue tracker: GitHub\n\n## Conventions\n")
        self.assertEqual(self.status()["tracker doc"][0], "drift")

    def test_a_freeform_tracker_is_unchecked(self):
        self.put("docs/agents/issue-tracker.md", "# Issues\n\nWe use Linear.\n")
        self.assertEqual(self.status()["tracker doc"][0], "unchecked")

    def test_legacy_context_names_drift(self):
        self.put("docs/agents/domain.md", "# Domain Docs\n\n- `CONTEXT.md`\n- `docs/adr/`\n")
        status, detail = self.status()["domain doc"]
        self.assertEqual(status, "drift")
        self.assertIn("CONTEXT.md", detail)

    def test_an_agent_skills_block_without_its_subsections_drifts(self):
        self.put("AGENTS.md", "# Agents\n\n## Agent skills\n\n### Issue tracker\n\nx\n")
        status, detail = self.status()["agent skills block"]
        self.assertEqual(status, "drift")
        self.assertIn("Domain Docs", detail)

    def test_a_missing_glossary_or_adr_directory_is_absent_not_drift(self):
        os.remove(os.path.join(self.repo, "GLOSSARY.md"))
        shutil.rmtree(os.path.join(self.repo, "docs/adr"))
        s = self.status()
        self.assertEqual(s["glossary"][0], "absent")
        self.assertEqual(s["ADRs"][0], "absent")
        self.assertEqual(s["domain doc"][0], "ok")

    def test_claude_md_is_read_first(self):
        self.put("CLAUDE.md", AGENTS.replace("# Agents", "# Claude"))
        status = self.status()["agent skills block"]
        self.assertEqual(status[0], "ok")
        self.assertEqual([p["path"] for p in self.detect()["pocock"]][0], "CLAUDE.md")


class TestWrite(Base):
    def test_writes_only_what_was_confirmed(self):
        code, out = run(write, self.repo, "--stack", "php", "--zone", "src/Security/**", "auth",
                        "--zone", "migrations/", "irreversible", "--no-gh")
        self.assertEqual(code, 0, out)
        text = self.read("docs/agents/review.md")
        self.assertIn("- php", text)
        self.assertIn("| `src/Security/**` | auth |", text)
        self.assertIn("| `migrations/` | irreversible |", text)
        self.assertNotIn("payments", text)
        self.assertNotIn("Controller", text)
        changed = git(self.repo, "status", "--porcelain").split("\n")
        self.assertEqual(sorted(x for x in changed if x), [" M AGENTS.md", "?? docs/agents/review.md"])

    def test_review_md_holds_no_tool_versions_and_no_run_root(self):
        run(write, self.repo, "--stack", "php", "--zone", "src/Security/**", "auth", "--no-gh")
        text = self.read("docs/agents/review.md")
        for tool in (shutil.which("git"), "deptrac", "roave", "found", self.state, ".local/state"):
            self.assertNotIn(tool, text)

    def test_the_review_subsection_goes_inside_the_block_and_nothing_else_moves(self):
        run(write, self.repo, "--stack", "php", "--no-gh")
        text = self.read("AGENTS.md")
        before, after = AGENTS.split("## Other section")
        self.assertTrue(text.startswith(before.rstrip("\n") + "\n\n### Review\n\n"), text)
        self.assertTrue(text.endswith("\n\n## Other section" + after), text)
        self.assertIn("See `docs/agents/review.md`.\n\n## Other section", text)

    def test_running_again_replaces_the_subsection_in_place(self):
        run(write, self.repo, "--stack", "php", "--no-gh")
        first = self.read("AGENTS.md")
        edited = first.replace("Stacks and risk map", "Old wording about stacks and risk map")
        with open(os.path.join(self.repo, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write(edited)
        run(write, self.repo, "--stack", "php", "--zone", "a/**", "auth", "--no-gh")
        self.assertEqual(self.read("AGENTS.md"), first)
        self.assertEqual(self.read("AGENTS.md").count("### Review"), 1)

    def test_a_review_subsection_in_the_middle_keeps_its_neighbours(self):
        middle = AGENTS.replace("### Domain docs", "### Review\n\nhand written\n\n### Domain docs")
        with open(os.path.join(self.repo, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write(middle)
        run(write, self.repo, "--stack", "php", "--no-gh")
        self.assertEqual(self.read("AGENTS.md"), middle.replace("hand written", write.repo_facts.SUBSECTION_BODY))

    def test_a_block_at_the_end_of_the_file(self):
        text = "# Agents\n\n## Agent skills\n\n### Issue tracker\n\nx\n"
        with open(os.path.join(self.repo, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write(text)
        run(write, self.repo, "--no-gh")
        self.assertEqual(self.read("AGENTS.md"), text + "\n### Review\n\n" + write.repo_facts.SUBSECTION_BODY + "\n")

    def test_crlf_line_endings_are_kept(self):
        with open(os.path.join(self.repo, "AGENTS.md"), "w", encoding="utf-8", newline="") as fh:
            fh.write(AGENTS.replace("\n", "\r\n"))
        run(write, self.repo, "--no-gh")
        text = self.read("AGENTS.md")
        self.assertNotIn("\n", text.replace("\r\n", ""))
        self.assertIn("### Review\r\n", text)

    def test_a_heading_inside_a_code_fence_is_not_the_block(self):
        fenced = "# Agents\n\n```markdown\n## Agent skills\n```\n"
        with open(os.path.join(self.repo, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write(fenced)
        code, out = run(write, self.repo, "--no-gh")
        self.assertEqual(code, 1)
        self.assertIn("no `## Agent skills` block", out)
        self.assertEqual(self.read("AGENTS.md"), fenced)


class TestRefusal(Base):
    def assertRefused(self, needle, *args):
        before = snapshot(self.repo)
        code, out = run(write, self.repo, "--stack", "php", "--zone", "src/**", "auth", *args)
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)
        self.assertIn("nothing written", out)
        self.assertEqual(snapshot(self.repo), before)

    def test_refuses_on_a_detached_head(self):
        git(self.repo, "checkout", "-q", "--detach")
        self.assertRefused("HEAD is detached", "--no-gh")
        self.assertFalse(self.detect()["guard"]["allowed"])

    def add_run(self, repo_key, branch_key, head="3c03254330c2", finished=True):
        d = os.path.join(self.state, "birdiz-review", "runs", repo_key, branch_key, head)
        os.makedirs(d)
        if finished:
            open(os.path.join(d, "run.json"), "w").close()

    def test_refuses_on_a_branch_review_pr_has_a_run_for(self):
        git(self.repo, "remote", "add", "origin", "git@github.com:acme/shop.git")
        git(self.repo, "checkout", "-q", "-b", "agent/issue-12")
        self.add_run("acme%2Fshop", "agent%2Fissue-12")
        self.assertRefused("review-pr has reviewed `agent/issue-12`", "--no-gh")

    def test_without_origin_the_repo_is_the_main_working_tree_name(self):
        git(self.repo, "checkout", "-q", "-b", "agent/issue-12")
        self.add_run("shop", "agent%2Fissue-12")
        self.assertRefused("review-pr has reviewed", "--no-gh")

    def test_unfinished_runs_and_other_branches_or_repos_do_not_refuse(self):
        git(self.repo, "remote", "add", "origin", "https://github.com/acme/shop.git")
        git(self.repo, "checkout", "-q", "-b", "setup-review")
        self.add_run("acme%2Fshop", "agent%2Fissue-12")
        self.add_run("acme%2Fother", "setup-review")
        self.add_run("acme%2Fshop", "setup-review", finished=False)
        self.add_run("acme%2Fshop", "setup-review", head=".3c03254330c2.tmp-42")
        code, out = run(write, self.repo, "--stack", "php", "--no-gh")
        self.assertEqual(code, 0, out)

    def test_refuses_on_the_head_of_an_open_pr(self):
        bindir = os.path.join(self.tmp, "bin")
        os.makedirs(bindir)
        gh = os.path.join(bindir, "gh")
        with open(gh, "w") as fh:
            fh.write("#!/bin/sh\necho '[{\"number\": 12, \"url\": \"https://example.invalid/pull/12\"}]'\n")
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)
        path = bindir + os.pathsep + os.environ.get("PATH", "")
        with unittest.mock.patch.dict(os.environ, {"PATH": path}):
            self.assertRefused("head of open PR #12")

    def test_refuses_malformed_input(self):
        self.assertRefused("negation", "--zone", "!x", "auth", "--no-gh")
        self.assertRefused("lowercase-hyphen", "--zone", "a/**", "Auth Zone", "--no-gh")
        self.assertRefused("listed twice", "--zone", "src/**", "auth", "--no-gh")

    def test_refuses_outside_a_git_work_tree(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        with open(os.path.join(plain, "AGENTS.md"), "w") as fh:
            fh.write(AGENTS)
        code, out = run(write, plain, "--no-gh")
        self.assertEqual(code, 1)
        self.assertIn("not a git work tree", out)
        self.assertFalse(os.path.exists(os.path.join(plain, "docs")))


class TestEntryPoints(unittest.TestCase):
    def test_they_run_under_isolated_mode_from_another_directory(self):
        for script in ("detect.py", "write.py"):
            done = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), "--help"],
                                  cwd=tempfile.gettempdir(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
            with self.subTest(script=script):
                self.assertEqual(done.returncode, 0, done.stderr)

    def test_an_unreadable_repo_exits_2(self):
        for module in (detect, write):
            with self.subTest(module=module.__name__):
                self.assertEqual(run(module, os.path.join(tempfile.gettempdir(), "no-such-repo-x"))[0], 2)


if __name__ == "__main__":
    unittest.main()
