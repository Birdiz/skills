"""Tests for validate.py on review runs: python3 -I -m unittest discover -s <this directory>

Each test writes a run directory by hand (header, detector outputs,
findings), writes its brief with brief.py, breaks one thing, and reads the
validator's report.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brief  # noqa: E402
import review_format as fmt  # noqa: E402
import validate  # noqa: E402

BASE, HEAD = "a" * 40, "b" * 40
DIFF = "%s..%s" % (BASE[:12], HEAD[:12])

FINDING = """### F-STR-001 Second HTTP client

```yaml
id: F-STR-001
axis: structure
status: unverified
severity: medium
confidence: high
sensitive: false
promptable: true
locations:
  - lib/http.py:1
diff: {diff}
attention: glance
blocks_merge: false
fan_in: unknown
```

**Evidence.** `lib/http.py:1` "import httpx" while the codebase uses requests.

**Reviewer question.** Is a second HTTP client wanted here?
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text, indent=2))


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def quiet(fn, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = fn(*args)
    return code, out.getvalue()


class TestValidate(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.root = os.path.join(tmp, "runs", "shop", "feature%2Fx", HEAD[:12])
        files = [{"path": "src/app.py", "change": "modified"}, {"path": "lib/http.py", "change": "added"},
                 {"path": "README.md", "change": "modified"}, {"path": "src/util.py", "change": "modified"},
                 {"path": "src/skipped.py", "change": "modified"}]
        self.header = {
            "schema": fmt.VERSION, "core": "finding-core@0.1.0", "repo": "shop", "branch": "feature/x",
            "target": "main..feature/x", "base": {"ref": "main", "sha": BASE},
            "head": {"ref": "feature/x", "sha": HEAD}, "merge_base": BASE, "diff": DIFF,
            "started": "2026-11-23T10:00:00Z",
            "tools": [{"name": "git", "command": "git", "found": True, "version": "2.47.0"},
                      {"name": "griffe", "command": "griffe", "found": True, "version": "1.5.0"}],
            "detectors": ["signals/git-changes.json", "signals/python-api.json"],
        }
        write(os.path.join(self.root, "run.json"), self.header)
        write(os.path.join(self.root, "signals", "git-changes.json"), {
            "detector": "git-changes", "version": fmt.VERSION, "content": False, "applies_to": ["*"],
            "files": files, "covered": [f["path"] for f in files], "not_covered": [],
            "signals": [{"path": "lib/http.py", "kind": "added", "reason": "added"}]})
        # A content detector for Python files: it covered every one but src/skipped.py.
        write(os.path.join(self.root, "signals", "python-api.json"), {
            "detector": "python-api", "version": "test@0", "content": True, "applies_to": ["*.py"],
            "tool": "griffe@1.5.0", "covered": ["src/app.py", "lib/http.py", "src/util.py"],
            "not_covered": [{"path": "src/skipped.py", "reason": "syntax error at line 3"}],
            "signals": [{"path": "src/util.py", "kind": "signature", "reason": "public function changed"}]})
        for axis in fmt.AXES:
            write(os.path.join(self.root, "findings", axis + ".md"), fmt.coverage_not_run(axis))
        write(os.path.join(self.root, "repo-" + HEAD[:12], "lib", "http.py"), "import httpx\n")
        self.add_finding("structure", FINDING.format(diff=DIFF))
        self.regenerate()

    # --- helpers --------------------------------------------------------------

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def add_finding(self, axis, text):
        p = self.path("findings", axis + ".md")
        write(p, read(p).replace("## Findings\n\nNone.\n", "## Findings\n\n" + text))

    def regenerate(self):
        code, out = quiet(brief.main, ["brief.py", self.root])
        self.assertEqual(code, 0, out)

    def edit(self, rel, old, new):
        text = read(self.path(rel))
        self.assertIn(old, text)
        write(self.path(rel), text.replace(old, new))

    def check(self, *args):
        return quiet(validate.main, ["validate.py", self.root] + list(args))

    def assertError(self, message, *args):
        code, report = self.check(*args)
        self.assertEqual(code, 1, report)
        self.assertIn(message, report)
        return report

    # --- the clean run ----------------------------------------------------------

    def test_a_clean_run_passes_and_each_file_lands_by_the_rules(self):
        code, report = self.check("--require", "brief")
        self.assertEqual(code, 0, report)
        self.assertIn("5 changed files (must-read 0, glance 2, skim 1, unproven 2), round 1", report)
        self.assertIn("PENDING verification findings/structure.md", report)
        text = read(self.path("brief.md"))
        self.assertIn("- `src/app.py`: covered by signals/python-api.json, with no signal;", text)
        self.assertIn("- `lib/http.py`: added (signals/git-changes.json); F-STR-001 Second HTTP client.", text)
        self.assertIn("- `src/util.py`: public function changed (signals/python-api.json).", text)
        self.assertIn("- `README.md`: no content detector reads this file type in this version.", text)
        self.assertIn("- `src/skipped.py`: signals/python-api.json applies but did not cover it:"
                      " syntax error at line 3.", text)
        self.assertIn("- signals/python-api.json did not cover `src/skipped.py`: syntax error at line 3.", text)
        self.assertIn("Proposed verdict: merge, round 1 (intent not checked", text)

    def test_the_round_count_reads_the_sibling_run_directories(self):
        other = os.path.join(os.path.dirname(self.root), "c" * 12)
        write(os.path.join(other, "run.json"), dict(self.header, head={"ref": "feature/x", "sha": "c" * 40}))
        self.assertIn("PENDING brief", self.check()[1])
        self.regenerate()
        self.assertIn("Proposed verdict: merge, round 2", read(self.path("brief.md")))
        self.assertEqual(self.check("--require", "brief")[0], 0)

    # --- the brief ------------------------------------------------------------------

    def test_a_stale_brief_is_pending_and_an_error_under_require_brief(self):
        self.edit("findings/structure.md", "attention: glance", "attention: must-read")
        code, report = self.check()
        self.assertEqual(code, 0, report)
        self.assertIn("PENDING brief", report)
        self.assertError("ERROR   brief brief.md  not the projection", "--require", "brief")
        self.regenerate()
        self.assertEqual(self.check("--require", "brief")[0], 0)
        self.assertIn("## Must read\n\n- `lib/http.py`\n  - F-STR-001", read(self.path("brief.md")))

    def test_skim_without_a_content_detector_is_an_error(self):
        self.edit("brief.md", "- `README.md`: no content detector reads this file type in this version.\n", "")
        self.edit("brief.md", "## Skim\n\n", "## Skim\n\n- `README.md`: covered by signals/git-changes.json, with no signal.\n")
        report = self.assertError("`README.md` is skim, but no content detector reads its file type")
        self.assertIn("signals/git-changes.json, which is not a content detector that covered it", report)

    def test_skim_needs_every_applicable_detector_no_signal_and_no_finding(self):
        for path, message in (("src/skipped.py", "applies to it and did not cover it"),
                              ("src/util.py", "signals/python-api.json signalled on it"),
                              ("lib/http.py", "F-STR-001 points at it")):
            with self.subTest(path=path):
                self.regenerate()
                text = read(self.path("brief.md"))
                line = next(l for l in text.split("\n") if l.startswith("- `%s`" % path))
                text = text.replace(line + "\n", "").replace(
                    "## Skim\n\n", "## Skim\n\n- `%s`: covered by signals/python-api.json, with no signal.\n" % path)
                write(self.path("brief.md"), text)
                self.assertError(message)

    def test_skim_without_proof_is_an_error(self):
        self.edit("brief.md", "covered by signals/python-api.json, with no signal;", "looks fine;")
        self.assertError("`src/app.py` is skim without the detector outputs that prove it")

    def test_each_changed_file_in_exactly_one_bucket(self):
        self.edit("brief.md", "## Glance\n\n", "## Glance\n\n- `src/app.py`: also here.\n- `ghost.py`: not changed.\n")
        report = self.assertError("`src/app.py` is in glance and in skim: one bucket per file")
        self.assertIn("`ghost.py` is in glance but is not a changed file", report)
        self.regenerate()
        self.edit("brief.md", "- `README.md`: no content detector reads this file type in this version.\n", "")
        self.assertError("changed file `README.md` is in no bucket")

    def test_must_read_needs_a_must_read_finding(self):
        self.edit("brief.md", "- `README.md`: no content detector reads this file type in this version.\n", "")
        self.edit("brief.md", "## Must read\n\nNone.", "## Must read\n\n- `README.md`")
        self.assertError("`README.md` is must-read, but no finding with `attention: must-read` points at it")

    def test_the_verdict_line_and_its_round_count(self):
        self.edit("brief.md", "Proposed verdict: merge, round 1 (", "Proposed verdict: merge (")
        self.assertError("the Verdict section needs one `Proposed verdict:")
        self.regenerate()
        self.edit("brief.md", "Proposed verdict: merge, round 1", "Proposed verdict: ship-it, round 1")
        self.assertError("the Verdict section needs one")

    def test_brief_sections_present_and_in_order(self):
        self.edit("brief.md", "## Coverage gaps", "## Gaps")
        self.assertError("section `## Coverage gaps` missing")
        self.regenerate()
        text = read(self.path("brief.md"))
        glance = text[text.index("## Glance"):text.index("## Skim")]
        write(self.path("brief.md"), text.replace(glance, "").replace("## Unproven", glance + "## Unproven"))
        self.assertError("sections out of order or repeated")

    def test_no_brief_is_an_error(self):
        os.remove(self.path("brief.md"))
        self.assertError("no brief: run brief.py")

    # --- the review extension of the finding --------------------------------------

    def test_review_keys(self):
        cases = [
            ("diff: %s" % DIFF, "diff: %s..%s" % ("c" * 12, HEAD[:12]), "is not this run's"),
            ("diff: %s" % DIFF, "diff: main..head", "is not `<base sha>..<head sha>`"),
            ("attention: glance", "attention: maybe", "attention `maybe` not in must-read | glance"),
            ("blocks_merge: false", "blocks_merge: no", "blocks_merge must be true or false"),
            ("fan_in: unknown", "fan_in: many", "fan_in `many` is not a count or `unknown`"),
            ("fan_in: unknown", "fan_in: unknown\ndeclared: two-way", "gives both `declared` and `detected`"),
            ("status: unverified", "status: confirmed", "no verifier exists in this version"),
            ("blocks_merge: false\n", "", "key `blocks_merge` missing"),
            ("\n**Reviewer question.** Is a second HTTP client wanted here?\n", "", "**Reviewer question.** missing"),
        ]
        for old, new, message in cases:
            with self.subTest(message=message):
                original = read(self.path("findings", "structure.md"))
                self.edit("findings/structure.md", old, new)
                self.regenerate()
                self.assertError(message)
                write(self.path("findings", "structure.md"), original)

    def test_a_disagreement_finding_tops_the_brief(self):
        self.edit("findings/structure.md", "fan_in: unknown", "fan_in: unknown\ndeclared: two-way\ndetected: one-way")
        self.regenerate()
        self.assertEqual(self.check("--require", "brief")[0], 0)
        text = read(self.path("brief.md"))
        self.assertIn("## Declared vs detected\n\n- F-STR-001 declared `two-way`, detected `one-way`", text)

    def test_axes_are_intent_contracts_structure(self):
        write(self.path("findings", "security.md"), fmt.coverage_not_run("intent"))
        self.assertError("`security` is not an axis of review-pr")
        os.remove(self.path("findings", "security.md"))
        self.add_finding("contracts", FINDING.format(diff=DIFF).replace("F-STR-001", "F-BRK-001")
                         .replace("axis: structure", "axis: contracts").replace("F-BRK-001 Second", "F-STR-002 Second"))
        self.regenerate()
        self.assertError("F-STR-002: ID does not follow F-BRK-<NNN> for this file")

    # --- the run header and detector outputs ---------------------------------------

    def test_the_header_lists_the_tools_with_versions(self):
        for tools, message in (([{"name": "griffe", "found": False}], "git included"),
                               ([{"name": "git", "found": True}], "when found, `version`"),
                               ([{"name": "git", "found": "yes", "version": "2"}], "needs `name`, `found`")):
            with self.subTest(message=message):
                write(self.path("run.json"), dict(self.header, tools=tools))
                self.assertError(message)
        write(self.path("run.json"), dict(self.header, tools=None, diff="nope"))
        report = self.assertError("diff `nope` is not `<base sha>..<head sha>`")
        self.assertIn("tools must list every detector tool", report)

    def test_the_run_directory_is_named_after_the_head(self):
        write(self.path("run.json"), dict(self.header, head={"ref": "x", "sha": "d" * 40}))
        self.assertError("not named after the head short sha dddddddddddd")

    def test_detector_outputs_carry_their_coverage(self):
        data = json.loads(read(self.path("signals", "python-api.json")))
        del data["not_covered"]
        data["content"] = "yes"
        write(self.path("signals", "python-api.json"), data)
        report = self.assertError("signals/python-api.json  key `not_covered` missing")
        self.assertIn("content must be true or false", report)

    def test_an_unreadable_header_cannot_be_validated(self):
        write(self.path("run.json"), "{not json")
        self.assertError("cannot read")


if __name__ == "__main__":
    unittest.main()
