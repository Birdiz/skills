"""Tests for the intent step's files, files in and files out:
python3 -I -m unittest discover -s <this directory>

A run on the fixture repository, with a spec (#35) and two tickets (#40 in
scope, #41 a sibling) served by the fake gh, writes the intent worksheet.
Each test then writes `findings/intent.md` as the step would, regenerates
the brief, and checks the run with validate.py and check-pointers.py. The
step's judgment itself is not tested here: only what the files must say.

The fixture branch modifies `src/app.py` (lines 1-2), adds
`lib/billing/invoice.py`, renames `README.md` to `README.txt` and deletes
`old.txt`. Ticket #40's criteria are lines 7 and 8 of its copy; the spec's
Implementation Decisions are lines 13-17 of its copy.
"""
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_run import GIT, check, entry, read  # noqa: E402
from test_sources import GhFixture, fixture, issue  # noqa: E402

AC1 = '#40 AC1 `sources/issue-40.md:7` "An unused link signs the customer in"'
AC2 = '#40 AC2 `sources/issue-40.md:8` "A used link is refused"'
FILES_OK = [("README.txt", "#40"), ("lib/billing/invoice.py", "#40 AC1"), ("old.txt", "#40"),
            ("src/app.py", "#40 AC1, #40 AC2")]


def finding(n, diff, locations, evidence, title="A used link is not refused", blocks="true"):
    return """### F-INT-%03d %s

```yaml
id: F-INT-%03d
axis: intent
status: unverified
severity: high
confidence: high
sensitive: false
promptable: true
locations:
%s
diff: %s
attention: must-read
blocks_merge: %s
fan_in: unknown
```

**Evidence.** %s

**Reviewer question.** Should a used link be refused, and where?
""" % (n, title, n, "\n".join("  - %s" % loc for loc in locations), diff, blocks, evidence)


MISSING_AC2 = ('`sources/issue-40.md:8` "A used link is refused" asks for it; '
               '`src/app.py:1` "def greet(name, punctuation):" refuses nothing.')


def intent_file(criteria, files, decisions=None, findings=(), axis="evaluated"):
    """The intent findings file as the step writes it."""
    out = ["# Intent", "", "## Coverage", "", "skill: review-pr@0.1.0, tools: []", "",
           "| Area | Status | Notes |", "|---|---|---|",
           "| Criteria to hunks | %s | |" % axis, "| Files to tickets or criteria | %s | |" % axis,
           "| Out of scope and decisions | %s | |" % axis, "", "Axis: %s" % axis, "", "## Criteria", "",
           "| Criterion | Status | Hunks | Finding |", "|---|---|---|---|"]
    out += ["| %s | %s | %s | %s |" % row for row in criteria]
    out += ["", "## Files", "", "| File | Justified by | Finding |", "|---|---|---|"]
    out += ["| `%s` | %s | %s |" % (row + ("",))[:3] for row in files]
    out += ["", "## Decisions", ""]
    if decisions:
        out += ["| Spec item | Change | Finding |", "|---|---|---|"] + ["| %s | %s | %s |" % r for r in decisions]
    else:
        out.append("None.")
    out += ["", "## Findings", ""] + (list(findings) or ["None.", ""]) + ["## Leads", "", "None.", ""]
    return "\n".join(out)


@unittest.skipIf(GIT is None, "git is not installed")
class TestIntent(unittest.TestCase):
    def setUp(self):
        self.fx = GhFixture(self)
        self.fx.gh_data["issues"]["35"] = issue(35, fixture("spec.md"), subs=[40, 41])
        self.fx.gh_data["issues"]["40"] = issue(40, fixture("ticket-issue-native.md"), parent=35)
        self.fx.gh_data["issues"]["41"] = issue(41, fixture("ticket-issue-body-relations.md"), parent=35)
        self.fx.save()

    def start(self, *spec):
        code, root, out = self.fx.run("feature/x", *(spec or ("--spec", "#40")))
        self.assertEqual(code, 0, out)
        self.diff = json.loads(read(os.path.join(root, "run.json")))["diff"]
        return root, out

    def write(self, root, text):
        with open(os.path.join(root, "findings", "intent.md"), "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out = entry("brief.py", root)
        self.assertEqual(code, 0, out)
        return out

    def assertRunOK(self, root):
        code, report = check(root, "--require", "brief", "--require", "intent")
        self.assertEqual(code, 0, report)
        self.assertIn("errors 0, warnings 0", report)
        code, report = entry("check-pointers.py", root)
        self.assertEqual(code, 0, report)

    def errors(self, root, text):
        self.write(root, text)
        code, report = check(root, "--require", "brief", "--require", "intent")
        self.assertEqual(code, 1, report)
        return report

    def test_the_worksheet_has_a_row_per_criterion_and_per_changed_file(self):
        root, out = self.start()
        self.assertIn("STEP: intent %s" % os.path.join(os.path.dirname(HERE), "steps", "intent.md"), out)
        self.assertIn("intent not checked: step not run yet", out)
        text = read(os.path.join(root, "findings", "intent.md"))
        self.assertIn("| %s | ? | | |" % AC1, text)
        self.assertIn("| %s | ? | | |" % AC2, text)
        self.assertNotIn("#41 AC", text, "a sibling ticket's criteria are not this PR's")
        for path in ("README.txt", "lib/billing/invoice.py", "old.txt", "src/app.py"):
            self.assertIn("| `%s` | ? | |" % path, text)
        self.assertIn("Axis: not-evaluable (step not run yet)", text)
        code, report = check(root, "--require", "brief")
        self.assertEqual(code, 0, report)
        self.assertIn("PENDING intent", report)
        code, report = check(root, "--require", "brief", "--require", "intent")
        self.assertEqual(code, 1, report)
        self.assertIn("the intent step has not run", report)
        self.assertEqual(entry("check-pointers.py", root)[0], 0, "the criteria's quotes are at their lines")
        self.assertTrue(os.path.isfile(os.path.join(root, "diff.patch")))

    def test_the_hunks_of_each_changed_file_are_recorded(self):
        root, _ = self.start()
        files = {f["path"]: f["hunks"] for f in
                 json.loads(read(os.path.join(root, "signals", "git-changes.json")))["files"]}
        self.assertEqual(files, {"src/app.py": [[1, 2]], "lib/billing/invoice.py": [[1, 1]],
                                 "README.txt": [], "old.txt": []})

    def test_every_criterion_found_and_every_file_justified_proposes_merge(self):
        root, _ = self.start()
        out = self.write(root, intent_file(
            [(AC1, "found", "`src/app.py:1-2`, `lib/billing/invoice.py:1`", ""),
             (AC2, "found", "`src/app.py:2`", "")], FILES_OK))
        self.assertIn("Proposed verdict: merge, round 1 (attention map only: contracts, structure, gates,"
                      " test integrity, adversarial not run).", out)
        self.assertRunOK(root)
        brief = read(os.path.join(root, "brief.md"))
        self.assertIn("- Intent: 2 of 2 acceptance criteria found, 0 partial, 0 not found; 4 of 4 changed files"
                      " justified, 0 out of scope; 0 change(s) against a stated decision.", brief)
        self.assertNotIn("- intent (`INT`)", brief.split("## Coverage gaps")[1])

    def test_a_criterion_not_found_is_a_must_read_item_and_a_fix(self):
        root, _ = self.start()
        out = self.write(root, intent_file(
            [(AC1, "found", "`src/app.py:1-2`", ""), (AC2, "not found", "", "F-INT-001")], FILES_OK[:3] +
            [("src/app.py", "#40 AC1")],
            findings=[finding(1, self.diff, ["sources/issue-40.md:8"], MISSING_AC2)]))
        self.assertIn("Proposed verdict: fix, round 1 (attention map only:", out,
                      "one criterion of two is not more than half")
        self.assertRunOK(root)
        must = read(os.path.join(root, "brief.md")).split("## Must read")[1].split("## ")[0]
        self.assertIn("- F-INT-001 `sources/issue-40.md:8`: A used link is not refused."
                      " **Question:** Should a used link be refused, and where?", must)

    def test_more_than_half_of_the_criteria_not_found_proposes_close_and_reprompt(self):
        root, _ = self.start()
        out = self.write(root, intent_file(
            [(AC1, "not found", "", "F-INT-001"), (AC2, "not found", "", "F-INT-002")],
            [("README.txt", "#40"), ("lib/billing/invoice.py", "#40"), ("old.txt", "#40"), ("src/app.py", "#40")],
            findings=[finding(1, self.diff, ["sources/issue-40.md:7"],
                              '`sources/issue-40.md:7` "An unused link signs the customer in" is not done.',
                              title="No sign-in by link"),
                      finding(2, self.diff, ["sources/issue-40.md:8"], MISSING_AC2)]))
        self.assertIn("Proposed verdict: close-and-reprompt, round 1", out)
        self.assertRunOK(root)
        verdict = read(os.path.join(root, "brief.md")).split("## Verdict")[1]
        self.assertIn("- Intent misread: 2 of 2 acceptance criteria not found (#40 AC1, #40 AC2).", verdict)

    def test_a_file_out_of_scope_proposes_close_and_reprompt(self):
        root, _ = self.start()
        out = self.write(root, intent_file(
            [(AC1, "found", "`src/app.py:1-2`", ""), (AC2, "found", "`src/app.py:2`", "")],
            FILES_OK[:1] + [("lib/billing/invoice.py", "out of scope", "F-INT-001")] + FILES_OK[2:],
            findings=[finding(1, self.diff, ["lib/billing/invoice.py:1"],
                              '`lib/billing/invoice.py:1` "TOTAL = 1" is billing, which no ticket asks for.',
                              title="Billing changed", blocks="false")]))
        self.assertIn("Proposed verdict: close-and-reprompt, round 1", out)
        self.assertRunOK(root)
        brief = read(os.path.join(root, "brief.md"))
        self.assertIn("- Out-of-scope edits beyond the touched tickets: `lib/billing/invoice.py` (F-INT-001).", brief)
        self.assertIn("- `lib/billing/invoice.py`\n  - F-INT-001 `lib/billing/invoice.py:1`: Billing changed.",
                      brief.split("## Must read")[1])

    def test_a_change_against_a_stated_decision_proposes_close_and_reprompt(self):
        root, _ = self.start()
        decision = ('`sources/issue-35.md:16` "A link is single use."', "`src/app.py:1-2`", "F-INT-001")
        out = self.write(root, intent_file(
            [(AC1, "found", "`src/app.py:1-2`", ""), (AC2, "found", "`src/app.py:2`", "")], FILES_OK,
            decisions=[decision],
            findings=[finding(1, self.diff, ["src/app.py:1", "sources/issue-35.md:16"],
                              '`sources/issue-35.md:16` "A link is single use." is decided; `src/app.py:1`'
                              ' "def greet(name, punctuation):" reuses it.', title="Links reused")]))
        self.assertIn("Proposed verdict: close-and-reprompt, round 1", out)
        self.assertRunOK(root)
        self.assertIn("- Work against the spec's stated decisions: F-INT-001 (src/app.py:1-2).",
                      read(os.path.join(root, "brief.md")))
        # an item outside Implementation Decisions and Out of Scope is not a decision
        report = self.errors(root, intent_file(
            [(AC1, "found", "`src/app.py:1-2`", ""), (AC2, "found", "`src/app.py:2`", "")], FILES_OK,
            decisions=[('`sources/issue-35.md:20` "Test through the sign-in endpoint."', "`src/app.py:1`",
                        "F-INT-001")],
            findings=[finding(1, self.diff, ["src/app.py:1"], '`src/app.py:1` "def greet(name, punctuation):"')]))
        self.assertIn("`sources/issue-35.md:20` is in neither Implementation Decisions nor Out of Scope", report)

    def test_the_rows_are_checked_against_the_sources_and_the_hunks(self):
        root, _ = self.start()
        report = self.errors(root, intent_file(
            [(AC1, "found", "`src/app.py:9`, `old.txt:1`, `README.txt`, `src/app.py`", ""),
             ("#41 AC1", "found", "`src/app.py:1`", "")],
            [("README.txt", "#41"), ("lib/billing/invoice.py", "?"), ("src/app.py", "#40 AC1, #99"),
             ("src/app.py", "out of scope")],
            findings=[finding(1, self.diff, ["sources/issue-40.md:8"], MISSING_AC2)]))
        for message in ("`src/app.py:9`: no hunk of `src/app.py` meets these lines (hunks 1-2)",
                        "`old.txt:1`: a deleted file has no lines in the head, give the path alone",
                        "`src/app.py`: give the hunk's lines, `src/app.py:<start>-<end>`",
                        "#41 AC1 is not an acceptance criterion of an in-scope ticket in sources.json",
                        "#40 AC2 has no row in `## Criteria`",
                        "`README.txt` is justified by #41, a sibling ticket: that is out of scope, flag it",
                        "`lib/billing/invoice.py`: justification left `?`",
                        "`src/app.py` is justified by #99, which is not an in-scope ticket, criterion or the spec",
                        "`src/app.py` has two rows",
                        "`src/app.py` (out of scope) needs the finding that says why",
                        "changed file `old.txt` has no row in `## Files`",
                        "F-INT-001 is cited by no row of Criteria, Files or Decisions"):
            self.assertIn(message, report)
        self.assertNotIn("`README.txt`: give the hunk's lines", report, "a pure rename has no line hunk")

    def test_a_status_must_match_its_hunks_and_findings(self):
        root, _ = self.start()
        report = self.errors(root, intent_file(
            [(AC1, "partial", "", ""), (AC2, "not found", "`src/app.py:1`", "F-INT-009")], FILES_OK))
        self.assertIn("#40 AC1 is partial but names no hunk", report)
        self.assertIn("#40 AC1 (partial) needs the finding that says why", report)
        self.assertIn("#40 AC2 is not found but names hunks", report)
        self.assertIn("#40 AC2 (not found) cites F-INT-009, which is not a finding of this file", report)

    def test_without_a_spec_intent_is_not_checked_and_misread_intent_is_not_offered(self):
        root, out = self.start("--no-spec")
        self.assertNotIn("STEP:", out)
        self.assertIn("Proposed verdict: merge, round 1 (intent not checked: no spec: the user said there is none;"
                      " contracts, structure, gates, test integrity, adversarial not run).", out)
        text = read(os.path.join(root, "findings", "intent.md"))
        self.assertIn("Axis: not-evaluable (no spec: the user said there is none)", text)
        self.assertNotIn("## Criteria", text)
        self.assertRunOK(root)
        # tables written anyway are refused, and never make a verdict
        report = self.errors(root, intent_file([(AC1, "not found", "", "")], FILES_OK))
        self.assertIn("intent is evaluated, but its sources are not-evaluable (no spec: the user said there is none)",
                      report)
        self.assertIn("Proposed verdict: merge", read(os.path.join(root, "brief.md")))

    def test_a_drifted_ticket_leaves_intent_not_checked(self):
        self.fx.gh_data["issues"]["40"] = issue(40, fixture("ticket-renamed.md"), parent=35)
        self.fx.save()
        root, out = self.start()
        self.assertNotIn("STEP:", out)
        self.assertIn("(intent not checked: contract drift: ticket #40, no `## Acceptance criteria` section;", out)
        self.assertRunOK(root)


if __name__ == "__main__":
    unittest.main()
