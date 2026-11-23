"""Tests for the spec, the tickets and the Pocock contract, files in and files
out: python3 -I -m unittest discover -s <this directory>

The contract tests read the fixture artifacts in `fixtures/pocock/`, one per
template. The run tests build a tiny repository, put a fake `gh` first on
the PATH that answers from a JSON file (pull requests, issues, sub-issues),
run run.py as the skill does, then read `sources.json` and the brief and
check the run with validate.py.
"""
import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pocock  # noqa: E402
from test_run import GIT, Fixture, check, git, read, write  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "pocock")

FAKE_GH = r'''#!{python} -I
import json, re, sys
with open({fixture!r}) as fh:
    data = json.load(fh)
args = sys.argv[1:]
with open({log!r}, "a") as fh:
    fh.write(" ".join(args) + "\n")


def fail(message):
    sys.stderr.write(message + "\n")
    sys.exit(1)


def pick(item, fields):
    return {{k: item[k] for k in fields if k in item}}


if args[:2] == ["pr", "view"]:
    pr = data.get("prs", {{}}).get(args[2]) or fail("no pull requests found for #" + args[2])
    print(json.dumps(pr))
elif args[:2] == ["issue", "view"]:
    fields = args[args.index("--json") + 1].split(",")
    if not data.get("native", True) and ("parent" in fields or "subIssues" in fields):
        fail('Unknown JSON field: "parent"')
    issue = data.get("issues", {{}}).get(args[2]) or fail("Could not resolve to an issue with the number of " + args[2])
    print(json.dumps(pick(issue, fields)))
elif args[:2] == ["issue", "list"]:
    n = re.search(r"#(\d+)", args[args.index("--search") + 1]).group(1)
    fields = args[args.index("--json") + 1].split(",")
    print(json.dumps([pick(i, fields) for i in data.get("issues", {{}}).values()
                      if "Part of #" + n in (i.get("body") or "")]))
else:
    fail("unexpected gh call: " + " ".join(args))
'''


def fixture(name):
    return read(os.path.join(FIXTURES, name))


def issue(number, body, parent=None, subs=()):
    return {"number": number, "title": "Issue %d" % number, "body": body, "state": "OPEN", "labels": [],
            "url": "https://github.com/acme/shop/issues/%d" % number,
            "parent": {"number": parent} if parent else None,
            "subIssues": {"nodes": [{"number": n} for n in subs], "totalCount": len(subs)}}


class TestContract(unittest.TestCase):
    """Each fixture artifact parses in its template, without drift."""

    def test_a_spec_in_the_to_spec_template(self):
        spec = pocock.read_artifact(fixture("spec.md"))
        self.assertEqual((spec["role"], spec["drift"]), ("spec", []))
        self.assertEqual(sorted(spec["sections"]), ["Implementation Decisions", "Out of Scope", "Testing Decisions"])

    def test_tickets_in_both_templates_and_both_kinds_of_relations(self):
        body = pocock.read_artifact(fixture("ticket-issue-body-relations.md"))
        self.assertEqual((body["role"], body["template"], body["drift"]), ("ticket", "issue", []))
        self.assertEqual((body["parent"], body["blocked_by"]), (35, [39]))
        self.assertEqual([c["text"] for c in body["criteria"]],
                         ["A link is sent to a known address", "An unknown address gets the same answer"])
        native = pocock.read_artifact(fixture("ticket-issue-native.md"))
        self.assertEqual((native["template"], native["drift"], native["parent"]), ("issue", [], None),
                         "no Parent or Blocked by section is not drift: they are native relations")
        self.assertEqual([c["checked"] for c in native["criteria"]], [False, True])
        local = pocock.read_artifact(fixture("ticket-local.md"))
        self.assertEqual((local["template"], local["drift"], len(local["criteria"])), ("local", [], 2))

    def test_pr_bodies_with_and_without_merge_danger(self):
        declared = pocock.read_pr_body(fixture("pr-merge-danger.md"))
        self.assertEqual((declared["status"], declared["door"], declared["blast_radius"], declared["drift"]),
                         ("declared", "two-way", "local", []))
        plain = pocock.read_pr_body(fixture("pr-plain.md"))
        self.assertEqual((plain["status"], plain["drift"]), ("not declared", []))
        odd = pocock.read_pr_body(fixture("pr-door-drift.md"))
        self.assertEqual(odd["status"], "drift")
        self.assertIn("Door `revolving` is neither one-way nor two-way", odd["drift"])

    def test_a_renamed_section_is_drift(self):
        ticket = pocock.read_artifact(fixture("ticket-renamed.md"))
        self.assertEqual(ticket["drift"], ["no `## Acceptance criteria` section"])
        spec = pocock.read_artifact(fixture("spec-renamed.md"))
        self.assertEqual(spec["drift"], ["no `## Out of Scope` section"])

    def test_closing_references_take_one_keyword_each(self):
        body = "Closes #40, #41\nfixes: #42\nResolves acme/shop#43\nCloses other/repo#44\n" \
               "Fixes https://github.com/acme/shop/issues/45\nSee #46"
        self.assertEqual(pocock.closing_refs(body, "acme/shop"), [40, 42, 43, 45])

    def test_the_tracker_doc_templates(self):
        self.assertEqual(pocock.tracker_doc(fixture("tracker-github.md"))["status"], "ok")
        self.assertEqual(pocock.tracker_doc(fixture("tracker-local.md"))["kind"], "Local Markdown")
        self.assertEqual(pocock.tracker_doc(None)["status"], "missing")


class GhFixture(Fixture):
    """The run fixture, with a tracker doc at the base and a fake gh."""

    def __init__(self, test, tracker="tracker-github.md"):
        super().__init__(test)
        self.gh_data = {"prs": {}, "issues": {}, "native": True}
        self.log = os.path.join(self.tmp, "gh.log")
        if tracker:
            write(self.repo, "docs/agents/issue-tracker.md", fixture(tracker))
            git(self.repo, "add", "-A")
            self.base = git(self.repo, "commit", "-qm", "tracker doc")
        path = os.path.join(self.bin, "gh")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(FAKE_GH.format(python=sys.executable, fixture=os.path.join(self.tmp, "gh.json"), log=self.log))
        os.chmod(path, 0o755)
        self.save()

    def save(self):
        with open(os.path.join(self.tmp, "gh.json"), "w", encoding="utf-8") as fh:
            json.dump(self.gh_data, fh)

    def issues(self, *items):
        for i in items:
            self.gh_data["issues"][str(i["number"])] = i
        self.save()

    def magic_link(self):
        """Spec #35 with sub-issues #40 and #41."""
        self.issues(issue(35, fixture("spec.md"), subs=(40, 41)),
                    issue(40, fixture("ticket-issue-body-relations.md"), parent=35),
                    issue(41, fixture("ticket-issue-native.md"), parent=35))

    def sources(self, root):
        return json.loads(read(os.path.join(root, "sources.json")))


def by_ref(found):
    return {a["ref"]: a for a in found["artifacts"]}


@unittest.skipIf(GIT is None, "git is not installed")
class TestPullRequest(unittest.TestCase):
    def setUp(self):
        self.fx = GhFixture(self)
        fx = self.fx
        # the PR's head lives only on the remote, as refs/pull/7/head
        self.origin = os.path.join(fx.tmp, "origin.git")
        git(fx.tmp, "init", "-q", "--bare", self.origin)
        git(fx.repo, "push", "-q", self.origin, "main", "feature/x:refs/pull/7/head")
        self.clone = os.path.join(fx.tmp, "clone")
        git(fx.tmp, "clone", "-q", "--no-local", self.origin, self.clone)
        fx.repo = self.clone
        fx.magic_link()
        self.pr(fixture("pr-merge-danger.md"))

    def pr(self, body):
        self.fx.gh_data["prs"]["7"] = {
            "number": 7, "title": "Magic link", "body": body, "url": "https://github.com/acme/shop/pull/7",
            "state": "OPEN", "baseRefName": "main", "baseRefOid": self.fx.base, "headRefName": "feature/x",
            "headRefOid": self.fx.head, "closingIssuesReferences": []}
        self.fx.save()

    def refs(self):
        done = subprocess.run([GIT, "-C", self.clone, "for-each-ref", "--format=%(refname) %(objectname)"],
                              stdout=subprocess.PIPE, universal_newlines=True)
        return done.stdout

    def test_a_pr_number_fetches_its_head_by_ref_without_a_checkout(self):
        self.assertNotEqual(subprocess.run([GIT, "-C", self.clone, "cat-file", "-e", self.fx.head]).returncode, 0)
        refs, head = self.refs(), read(os.path.join(self.clone, ".git", "HEAD"))
        code, root, out = self.fx.run("--pr", "7")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.refs(), refs, "no ref written")
        self.assertEqual(read(os.path.join(self.clone, ".git", "HEAD")), head, "nothing checked out")
        self.assertFalse(os.path.exists(os.path.join(self.clone, "src", "app.py.orig")))
        self.assertNotIn("punctuation", read(os.path.join(self.clone, "src", "app.py")))
        header = json.loads(read(os.path.join(root, "run.json")))
        self.assertEqual((header["head"]["sha"], header["branch"]), (self.fx.head, "feature/x"))
        self.assertEqual((header["pr"]["number"], header["pr"]["fetched"]), (7, ["refs/pull/7/head"]))
        self.assertEqual(os.path.basename(os.path.dirname(root)), "feature%2Fx")
        code, report = check(root, "--require", "brief")
        self.assertEqual(code, 0, report)

    def test_closing_references_lead_to_the_ticket_its_spec_and_its_siblings(self):
        code, root, out = self.fx.run("--pr", "7")
        self.assertEqual(code, 0, out)
        found = self.fx.sources(root)
        self.assertEqual(found["found_by"], "closing references in the PR body")
        arts = by_ref(found)
        self.assertEqual((arts["#40"]["scope"], arts["#40"]["status"]), ("in scope", "ok"))
        self.assertEqual((arts["#35"]["role"], arts["#35"]["found_by"]), ("spec", "parent of #40"))
        self.assertEqual(arts["#35"]["tickets_by"], "sub-issues")
        self.assertEqual((arts["#41"]["scope"], arts["#41"]["found_by"]), ("sibling", "sub-issue of #35"))
        self.assertEqual(found["dimensions"]["intent"], "evaluable")
        self.assertEqual(read(os.path.join(root, arts["#40"]["file"])), fixture("ticket-issue-body-relations.md"))
        brief = read(os.path.join(root, "brief.md"))
        self.assertIn("- Spec and tickets: closing references in the PR body: spec #35 (tickets by sub-issues);"
                      " in scope #40; 1 sibling ticket(s).", brief)
        self.assertIn("- Intent sources: evaluable.", brief)
        self.assertIn("- Pocock artifacts checked against %s." % pocock.UPSTREAM, brief)
        self.assertIn("## Declared vs detected\n\nDeclared in PR #7: Door `two-way`, Blast Radius `local`.\n"
                      "Not compared: the contracts step, which detects it, did not run.", brief)
        self.assertIn("sources: Intent sources: evaluable.", out)
        self.assertNotIn("ASK:", out)

    def test_a_pr_body_without_merge_danger_is_not_declared(self):
        self.pr(fixture("pr-plain.md"))
        code, root, out = self.fx.run("--pr", "7")
        self.assertEqual(code, 0, out)
        found = self.fx.sources(root)
        self.assertEqual((found["pr"]["status"], found["dimensions"]["declared"]), ("not declared", "not declared"))
        self.assertEqual(by_ref(found)["#41"]["scope"], "in scope", "both closed tickets are in scope")
        self.assertIn("Risk not declared: the body of PR #7 has no `Merge Danger` section.",
                      read(os.path.join(root, "brief.md")))
        self.assertEqual(check(root, "--require", "brief")[0], 0)

    def test_an_unreadable_door_is_contract_drift(self):
        self.pr(fixture("pr-door-drift.md") + "\nCloses #40\n")
        code, root, out = self.fx.run("--pr", "7")
        found = self.fx.sources(root)
        self.assertEqual(found["dimensions"]["declared"],
                         "not-evaluable (contract drift: PR #7 body, Door `revolving` is neither one-way nor two-way)")
        self.assertIn("Declared risk not read: PR #7 body, contract drift:", read(os.path.join(root, "brief.md")))

    def test_an_unknown_pr_is_refused(self):
        code, root, out = self.fx.run("--pr", "8")
        self.assertEqual(code, 2, out)
        self.assertIn("PR #8", out)
        self.assertIsNone(root)


@unittest.skipIf(GIT is None, "git is not installed")
class TestOrder(unittest.TestCase):
    def setUp(self):
        self.fx = GhFixture(self)

    def test_issue_references_in_commits_when_there_is_no_pr(self):
        self.fx.magic_link()
        wt = os.path.join(self.fx.tmp, "wt")
        git(self.fx.repo, "worktree", "add", "-q", wt, "feature/x")
        write(wt, "src/link.py", "x = 1\n")
        git(wt, "add", "-A")
        git(wt, "commit", "-qm", "Send the link (#41)")
        git(self.fx.repo, "worktree", "remove", "--force", wt)
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        found = self.fx.sources(root)
        self.assertEqual(found["found_by"], "issue references in commits")
        arts = by_ref(found)
        self.assertEqual((arts["#41"]["scope"], arts["#40"]["scope"], found["spec"]), ("in scope", "sibling", "#35"))
        self.assertIn("Risk not declared: no PR body was read", read(os.path.join(root, "brief.md")))

    def test_nothing_found_asks_the_user(self):
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        found = self.fx.sources(root)
        self.assertIsNone(found["found_by"])
        self.assertEqual(found["dimensions"]["intent"], "not-evaluable (no spec found)")
        self.assertIn("ASK: no spec found: ask the user where it is", out)
        self.assertEqual(out.strip().split("\n")[-1], "RUN: %s" % root)
        self.assertEqual(check(root, "--require", "brief")[0], 0)

    def test_the_users_answer(self):
        self.fx.magic_link()
        code, root, out = self.fx.run("feature/x", "--spec", "#35")
        self.assertEqual(code, 0, out)
        found = self.fx.sources(root)
        self.assertEqual((found["found_by"], found["spec"]), ("named by the user", "#35"))
        self.assertEqual({a["ref"]: a["scope"] for a in found["artifacts"]},
                         {"#35": "spec", "#40": "in scope", "#41": "in scope"},
                         "the spec itself is in scope: every ticket is")
        code, root, out = self.fx.run("feature/x", "--no-spec")
        found = self.fx.sources(root)
        self.assertEqual(found["dimensions"]["intent"], "not-evaluable (no spec: the user said there is none)")
        self.assertNotIn("ASK:", out)

    def test_part_of_lines_when_gh_has_no_sub_issues(self):
        self.fx.gh_data["native"] = False
        self.fx.issues(issue(35, fixture("spec.md")),
                       issue(40, "Part of #35\n\n" + fixture("ticket-issue-native.md")),
                       issue(41, "Part of #35\n\n" + fixture("ticket-issue-native.md")),
                       issue(42, "Part of #350\n\n" + fixture("ticket-issue-native.md")))
        code, root, out = self.fx.run("feature/x", "--spec", "35")
        found = self.fx.sources(root)
        self.assertEqual(sorted(by_ref(found)), ["#35", "#40", "#41"])
        self.assertEqual(by_ref(found)["#35"]["tickets_by"], "`Part of #35` lines")
        self.assertEqual(found["dimensions"]["intent"], "evaluable")

    def test_an_old_format_spec_and_new_format_tickets_are_each_checked_when_read(self):
        # #40 carries its relations as body text (Parent, Blocked by), #41 natively
        self.fx.magic_link()
        code, root, out = self.fx.run("feature/x", "--spec", "#35")
        arts = by_ref(self.fx.sources(root))
        self.assertEqual([arts[r]["status"] for r in ("#35", "#40", "#41")], ["ok", "ok", "ok"])
        self.assertEqual(arts["#41"]["relations"], {"native": True, "parent": 35, "sub_issues": []})

    def test_a_renamed_section_makes_intent_not_evaluable_and_the_run_continues(self):
        self.fx.issues(issue(35, fixture("spec.md"), subs=(40, 41)),
                       issue(40, fixture("ticket-renamed.md"), parent=35),
                       issue(41, fixture("ticket-issue-native.md"), parent=35))
        code, root, out = self.fx.run("feature/x", "--spec", "#35")
        self.assertEqual(code, 0, out)
        found = self.fx.sources(root)
        self.assertEqual(found["dimensions"]["intent"],
                         "not-evaluable (contract drift: ticket #40, no `## Acceptance criteria` section)")
        self.assertEqual(by_ref(found)["#41"]["status"], "ok")
        brief = read(os.path.join(root, "brief.md"))
        self.assertIn("- Intent sources: not-evaluable (contract drift: ticket #40,", brief)
        self.assertIn("in scope #40, contract drift, #41", brief)
        self.assertEqual(check(root, "--require", "brief")[0], 0)

    def test_without_a_tracker_doc_issues_are_not_read(self):
        fx = GhFixture(self, tracker=None)
        fx.magic_link()
        code, root, out = fx.run("feature/x", "--spec", "#35")
        found = fx.sources(root)
        self.assertEqual(found["dimensions"]["intent"],
                         "not-evaluable (no tracker doc at the base (docs/agents/issue-tracker.md))")
        self.assertFalse(os.path.exists(fx.log), "gh is not asked")
        self.assertEqual(check(root, "--require", "brief")[0], 0)


@unittest.skipIf(GIT is None, "git is not installed")
class TestLocalTracker(unittest.TestCase):
    def test_a_spec_file_named_after_the_branch_and_its_ticket_files(self):
        fx = GhFixture(self, tracker="tracker-local.md")
        wt = os.path.join(fx.tmp, "wt")
        git(fx.repo, "worktree", "add", "-q", "-b", "feature/magic-link-3fa9c1", wt, "feature/x")
        write(wt, ".scratch/magic-link/spec.md", fixture("spec.md"))
        write(wt, ".scratch/magic-link/issues/01-send-the-link.md", fixture("ticket-local.md"))
        write(wt, ".scratch/other/spec.md", fixture("spec.md"))
        git(wt, "add", "-A")
        git(wt, "commit", "-qm", "Spec and ticket (#12)")
        git(fx.repo, "worktree", "remove", "--force", wt)
        code, root, out = fx.run("feature/magic-link-3fa9c1")
        self.assertEqual(code, 0, out)
        found = fx.sources(root)
        self.assertEqual(found["found_by"], "spec file matching the branch", "a local tracker reads no `#12`")
        arts = by_ref(found)
        ticket = arts[".scratch/magic-link/issues/01-send-the-link.md"]
        self.assertEqual((ticket["template"], ticket["status"], ticket["scope"]), ("local", "ok", "in scope"))
        self.assertEqual(found["spec"], ".scratch/magic-link/spec.md")
        self.assertEqual(found["dimensions"]["intent"], "evaluable")
        self.assertFalse(os.path.exists(fx.log), "gh is not asked")
        self.assertEqual(check(root, "--require", "brief")[0], 0)


if __name__ == "__main__":
    unittest.main()
