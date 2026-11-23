"""Tests for the contracts step's files, files in and files out:
python3 -I -m unittest discover -s <this directory>

The intent fixture (spec #35, ticket #40 in scope, served by the fake gh)
gains a migration that drops a column, and pull request #7 whose body
declares a two-way Door. A run writes the contracts worksheet; each test
fills it as the step would (and the intent worksheet, when the verdict
needs sound intent), regenerates the brief, and checks the run with
validate.py and check-pointers.py. The step's judgment itself is not
tested here: only what the files must say.
"""
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_intent import AC1, AC2, FILES_OK, intent_file  # noqa: E402
from test_run import GIT, check, entry, git, read, write  # noqa: E402
from test_sources import GhFixture, fixture, issue  # noqa: E402

MIGRATION = "db/migrations/002_drop_email.sql"
DROP = '`%s:1` "ALTER TABLE users DROP COLUMN email;"' % MIGRATION
AREAS = ["Code API", "Routes and wire contracts", "Persistence", "Configuration", "Behaviour (assertions)",
         "Fan-in", "Declared vs detected"]


def finding(n, diff, locations, evidence, title="Migration drops the email column", attention="must-read",
            blocks="true", extra=""):
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
%s
diff: %s
attention: %s
blocks_merge: %s
fan_in: unknown
%s```

**Evidence.** %s

**Reviewer question.** Is losing the stored addresses acceptable?
""" % (n, title, n, "\n".join("  - %s" % loc for loc in locations), diff, attention, blocks, extra, evidence)


def fill(sheet, judgments, detected, declared_findings="", findings=(), axis="evaluated"):
    """The contracts worksheet as the step fills it: `judgments` maps a
    signal ID to (judgment, findings cell)."""
    out = []
    section = None
    for line in sheet.split("\n"):
        if line.startswith("## "):
            section = line[3:]
        if section == "Coverage" and "| not-evaluable | Step not run yet" in line:
            line = "| %s | %s | |" % (line.split("|")[1].strip(), axis)
        elif line.startswith("Axis: "):
            line = "Axis: %s" % axis
        elif section == "Signals" and line.startswith("| S"):
            sid = line[2:].split(" ", 1)[0]
            if sid in judgments:
                line = line[:line.rindex("| ? | |")] + "| %s | %s |" % judgments[sid]
        elif section == "Declared" and line.endswith("| ? | |"):
            line = line[:line.rindex("| ? | |")] + "| %s | %s |" % (detected, declared_findings)
        out.append(line)
    text = "\n".join(out)
    if findings:
        text = text.replace("## Findings\n\nNone.\n", "## Findings\n\n" + "\n".join(findings))
    return text


@unittest.skipIf(GIT is None, "git is not installed")
class TestContracts(unittest.TestCase):
    def setUp(self):
        self.fx = GhFixture(self)
        self.fx.gh_data["issues"]["35"] = issue(35, fixture("spec.md"), subs=[40, 41])
        self.fx.gh_data["issues"]["40"] = issue(40, fixture("ticket-issue-native.md"), parent=35)
        self.fx.gh_data["issues"]["41"] = issue(41, fixture("ticket-issue-body-relations.md"), parent=35)
        self.fx.save()
        self.fx.head = self.fx.commit_on_branch(MIGRATION, "ALTER TABLE users DROP COLUMN email;\n")

    def pr(self, body):
        self.fx.gh_data["prs"]["7"] = {
            "number": 7, "title": "Magic link", "body": body, "url": "https://github.com/acme/shop/pull/7",
            "state": "OPEN", "baseRefName": "main", "baseRefOid": self.fx.base, "headRefName": "feature/x",
            "headRefOid": self.fx.head, "closingIssuesReferences": []}
        self.fx.save()

    def start(self, *args):
        code, root, out = self.fx.run(*(args or ("feature/x", "--spec", "#40")))
        self.assertEqual(code, 0, out)
        self.root, self.out = root, out
        self.diff = json.loads(read(os.path.join(root, "run.json")))["diff"]
        self.blank = self.sheet()
        return root

    def sheet(self):
        return read(os.path.join(self.root, "findings", "contracts.md"))

    def write(self, text, axis="contracts"):
        with open(os.path.join(self.root, "findings", axis + ".md"), "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out = entry("brief.py", self.root)
        self.assertEqual(code, 0, out)
        return out

    def sound_intent(self):
        self.write(intent_file([(AC1, "found", "`src/app.py:1-2`", ""), (AC2, "found", "`src/app.py:2`", "")],
                               FILES_OK + [(MIGRATION, "#40")]), axis="intent")

    def drop(self, n=1, **kw):
        return finding(n, self.diff, ["%s:1" % MIGRATION], DROP + " drops the column.", **kw)

    def brief(self):
        return read(os.path.join(self.root, "brief.md"))

    def assertRunOK(self, *require):
        code, report = check(self.root, "--require", "brief", "--require", "contracts", *require)
        self.assertEqual(code, 0, report)
        self.assertIn("errors 0, warnings 0", report)
        code, report = entry("check-pointers.py", self.root)
        self.assertEqual(code, 0, report)

    def errors(self, text):
        self.write(text)
        code, report = check(self.root, "--require", "brief", "--require", "contracts")
        self.assertEqual(code, 1, report)
        return report

    # --- the worksheet ------------------------------------------------------------

    def test_the_worksheet_has_a_row_per_signal_and_the_declared_row(self):
        self.start()
        self.assertIn("STEP: contracts %s" % os.path.join(os.path.dirname(HERE), "steps", "contracts.md"), self.out)
        self.assertLess(self.out.index("STEP: intent"), self.out.index("STEP: contracts"))
        text = self.sheet()
        self.assertIn("| S1 `%s:1` migrations `drop`: drops a table, a column or another object, or empties a table"
                      " | ? | |" % MIGRATION, text)
        self.assertNotIn("| S2 ", text)
        self.assertIn("| not declared: no PR body read | ? | |", text)
        self.assertIn("Axis: not-evaluable (step not run yet)", text)
        code, report = check(self.root, "--require", "brief")
        self.assertEqual(code, 0, report)
        self.assertIn("PENDING contracts", report)
        code, report = check(self.root, "--require", "brief", "--require", "contracts")
        self.assertEqual(code, 1, report)
        self.assertIn("the contracts step has not run", report)
        self.assertEqual(entry("check-pointers.py", self.root)[0], 0, "the signals' pointers open in the head")

    def test_a_change_with_no_signal_still_gets_the_step(self):
        self.fx.head = self.fx.commit_on_branch(MIGRATION, "SELECT 1;\n")
        self.start("feature/x", "--no-spec")
        self.assertIn("STEP: contracts", self.out)
        self.assertIn("## Signals\n\nNone.\n", self.sheet())
        self.write(fill(self.blank, {}, "two-way"))
        self.assertRunOK()

    # --- the verdict ----------------------------------------------------------------

    def test_a_merge_blocking_finding_with_sound_intent_is_a_fix(self):
        self.start()
        self.sound_intent()
        out = self.write(fill(self.blank, {"S1": ("one-way", "F-BRK-001")}, "one-way",
                              findings=[self.drop()]))
        self.assertIn("Proposed verdict: fix, round 1 (attention map only: structure, gates, test integrity,"
                      " adversarial not run).", out)
        self.assertRunOK("--require", "intent")
        brief = self.brief()
        verdict = brief.split("## Verdict")[1]
        self.assertIn("- Blocks the merge: F-BRK-001 (%s:1)." % MIGRATION, verdict)
        self.assertIn("- Contracts: 1 signal(s) judged, 1 one-way, 0 breaking, 0 minor; detected Door one-way.",
                      verdict)
        self.assertIn("- Intent: 2 of 2 acceptance criteria found", verdict)
        must = brief.split("## Must read")[1].split("## ")[0]
        self.assertIn("- `%s`\n  - F-BRK-001 `%s:1`: Migration drops the email column. **Question:**" % (
            MIGRATION, MIGRATION), must)
        self.assertIn("| Door | no PR body read | `one-way` (S1) |", brief)
        self.assertNotIn("- contracts (`BRK`)", brief.split("## Coverage gaps")[1])

    def test_minor_signals_and_no_finding_propose_merge(self):
        self.start()
        out = self.write(fill(self.blank, {"S1": ("minor", "")}, "two-way"))
        self.assertIn("Proposed verdict: merge, round 1 (intent not checked: step not run yet; structure,", out)
        self.assertRunOK()
        self.assertIn("| Door | no PR body read | `two-way` |", self.brief())

    # --- declared vs detected ---------------------------------------------------------

    def test_a_declared_door_that_disagrees_tops_the_brief_beside_the_risk_zones(self):
        git(self.fx.repo, "checkout", "-q", "main")
        write(self.fx.repo, "docs/agents/review.md", "# Review\n\n## Stacks\n\n- python\n\n## Risk map\n\n"
              "| Glob | Zone |\n|---|---|\n| `db/**` | persistence |\n")
        git(self.fx.repo, "add", "-A")
        self.fx.base = git(self.fx.repo, "commit", "-qm", "risk map")
        self.pr(fixture("pr-merge-danger.md"))
        self.start("--pr", "7")
        self.assertIn("| PR #7: Door `two-way`, Blast Radius `local` | ? | |", self.sheet())
        disagree = finding(2, self.diff, ["%s:1" % MIGRATION, "sources/pr-7.md:15"],
                           DROP + ' is one-way, while `sources/pr-7.md:15` "**Door:** two-way" says otherwise.',
                           title="Declared two-way, the migration is one-way", blocks="false",
                           extra="declared: two-way\ndetected: one-way\n")
        self.write(fill(self.blank, {"S1": ("one-way", "F-BRK-001")}, "one-way", "F-BRK-002",
                        findings=[self.drop(), disagree]))
        self.assertRunOK()
        top = self.brief().split("## Declared vs detected\n\n")[1].split("## ")[0]
        self.assertEqual(top.split("\n")[:2], [
            "Declared in PR #7: Door `two-way`, Blast Radius `local`.",
            "- F-BRK-002 declared `two-way`, detected `one-way`: Declared two-way, the migration is one-way (%s:1)"
            % MIGRATION])
        self.assertIn("| Door | `two-way` | `one-way` (S1, F-BRK-002) |", top)
        self.assertIn("| Blast Radius | `local` | risk zones: persistence (`%s`); fan-in:" % MIGRATION, top)

    def test_a_disagreement_needs_its_finding_with_both_doors(self):
        self.pr(fixture("pr-merge-danger.md"))
        self.start("--pr", "7")
        report = self.errors(fill(self.blank, {"S1": ("one-way", "F-BRK-001")}, "one-way", findings=[self.drop()]))
        self.assertIn("the PR declares a two-way Door and the step detected one-way: the row cites the disagreement"
                      " finding, with `declared` and `detected`", report)
        wrong = finding(2, self.diff, ["%s:1" % MIGRATION], DROP, extra="declared: one-way\ndetected: two-way\n",
                        blocks="false")
        report = self.errors(fill(self.blank, {"S1": ("one-way", "F-BRK-001")}, "one-way", "F-BRK-002",
                                  findings=[self.drop(), wrong]))
        self.assertIn("F-BRK-002: declared `one-way`, detected `two-way`, but the PR declares `two-way` and the step"
                      " detected `one-way`", report)

    def test_agreeing_doors_need_no_disagreement(self):
        self.pr(fixture("pr-merge-danger.md"))
        self.start("--pr", "7")
        self.write(fill(self.blank, {"S1": ("minor", "")}, "two-way"))
        self.assertRunOK()
        self.assertIn("No disagreement between the declared risk and what was detected.", self.brief())
        extra = finding(1, self.diff, ["%s:1" % MIGRATION], DROP, extra="declared: two-way\ndetected: two-way\n",
                        attention="glance", blocks="false")
        report = self.errors(fill(self.blank, {"S1": ("minor", "")}, "two-way", findings=[extra]))
        self.assertIn("F-BRK-001 is a disagreement finding, but the declared and detected Doors agree", report)

    def test_without_a_declared_door_there_is_nothing_to_disagree_with(self):
        self.pr(fixture("pr-plain.md"))
        self.start("--pr", "7")
        self.assertIn("| not declared: PR #7 has no `Merge Danger` | ? | |", self.sheet())
        extra = finding(2, self.diff, ["%s:1" % MIGRATION], DROP, extra="declared: two-way\ndetected: one-way\n",
                        blocks="false")
        report = self.errors(fill(self.blank, {"S1": ("one-way", "F-BRK-001")}, "one-way", "F-BRK-002",
                                  findings=[self.drop(), extra]))
        self.assertIn("F-BRK-002 is a disagreement finding, but no Door was declared to disagree with", report)
        self.write(fill(self.blank, {"S1": ("one-way", "F-BRK-001")}, "one-way", findings=[self.drop()]))
        self.assertRunOK()
        top = self.brief().split("## Declared vs detected\n\n")[1].split("## ")[0]
        self.assertIn("Risk not declared: the body of PR #7 has no `Merge Danger` section.", top)
        self.assertIn("| Door | not declared | `one-way` (S1) |", top)

    # --- the rows checked against the run --------------------------------------------------

    def test_the_rows_are_checked_against_the_detector_outputs(self):
        self.start()
        sheet = self.blank.replace("| S1 `%s:1`" % MIGRATION, "| S1 `src/app.py:1`")
        sheet = sheet.replace("|---|---|---|\n| S1", "|---|---|---|\n| S9 `x.py` x `y`: z | minor | |\n| S1", 1)
        report = self.errors(fill(sheet, {"S1": ("breaking", "")}, "two-way"))
        for message in ("S9 is not a signal of this run's detectors",
                        "S1 is a signal on `%s`, not what this row names" % MIGRATION,
                        "S1 (breaking) needs the finding that says why"):
            self.assertIn(message, report)
        report = self.errors(fill(self.blank, {"S1": ("risky", "F-BRK-007")}, "?"))
        self.assertIn("S1: judgment `risky` not in one-way | breaking | minor", report)
        self.assertIn("the detected Door is left `?`", report)
        report = self.errors(fill(self.blank.replace("| S1 ", "| X1 "), {}, "two-way"))
        self.assertIn("S1 has no row in `## Signals`", report)

    def test_the_detected_door_follows_the_rows(self):
        self.start()
        report = self.errors(fill(self.blank, {"S1": ("one-way", "F-BRK-001")}, "two-way", findings=[self.drop()]))
        self.assertIn("the detected Door is two-way, but S1 is judged one-way", report)
        report = self.errors(fill(self.blank, {"S1": ("minor", "")}, "one-way"))
        self.assertIn("the detected Door is one-way, but no signal is judged one-way and the row cites no finding",
                      report)
        report = self.errors(fill(self.blank, {"S1": ("minor", "")}, "sideways"))
        self.assertIn("the detected Door `sideways` is not one-way or two-way", report)

    def test_the_tables_belong_to_the_contracts_file(self):
        self.start()
        path = os.path.join(self.root, "findings", "structure.md")
        write(os.path.dirname(path), "structure.md", read(path).replace("## Findings", "## Signals\n\nNone.\n\n## Findings"))
        code, report = check(self.root)
        self.assertIn("`## Signals` belongs to the contracts findings file", report)


if __name__ == "__main__":
    unittest.main()
