"""Tests for check-pointers.py: python3 -I -m unittest discover -s <this directory>"""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("check_pointers", os.path.join(HERE, "check-pointers.py"))
check_pointers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_pointers)

SOURCE = "\n".join(["one", "cookie_secure: false", "api_key = 'abc'", "function start() {", "  return run();", "}", "last"])


class CheckPointersTest(unittest.TestCase):
    def workspace(self, findings="", plan=None, map_text=None, files=None):
        root = tempfile.mkdtemp()
        all_files = {
            "00-engagement.md": "# Engagement\nworking_copy: clone\n",
            "findings/app-security.md": findings,
            "clone/src/app.py": SOURCE,
            "clone/CLAUDE.md": SOURCE,
            "repo-9f8e7d6/src/app.py": "later\ncookie_secure: true\n",
            "tool-output/privacy/law.txt": "Article 13\nthe text of the law\n",
        }
        if plan is not None:
            all_files["02-remediation-plan.md"] = plan
        if map_text is not None:
            all_files["01-codebase-map.md"] = map_text
        all_files.update(files or {})
        for name, text in all_files.items():
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        return root

    def run_on(self, *args, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check_pointers.main(["check-pointers.py", self.workspace(*args, **kw)])
        return code, out.getvalue()

    def assertClean(self, text, **kw):
        code, out = self.run_on(text, **kw)
        self.assertEqual(code, 0, out)
        self.assertIn("mismatch 0, missing 0", out)
        return out

    def test_quote_at_its_line(self):
        out = self.assertClean('`src/app.py:2` "`cookie_secure: false`"')
        self.assertIn("1 pointers opened", out)
        self.assertIn("1 with a quote", out)

    def test_file_outside_src(self):
        self.assertClean('CLAUDE.md:2 "cookie_secure"')

    def test_drifted_quote_says_where(self):
        code, out = self.run_on('src/app.py:5 "cookie_secure: false"')
        self.assertEqual(code, 1)
        self.assertIn("MISMATCH", out)
        self.assertIn("line 2", out)

    def test_invented_quote(self):
        code, out = self.run_on('src/app.py:2 "not in this file"')
        self.assertEqual(code, 1)
        self.assertIn("nowhere in the file", out)

    def test_missing_file(self):
        code, out = self.run_on("src/gone.py:2")
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)

    def test_line_past_the_end(self):
        code, out = self.run_on("src/app.py:99")
        self.assertEqual(code, 1)
        self.assertIn("the file has 7 lines", out)

    def test_range(self):
        self.assertClean('src/app.py:4-6 "return run()"')

    def test_quote_over_two_lines(self):
        self.assertClean('src/app.py:4 "function start() { return run();"')

    def test_quote_starting_after_its_line_fails(self):
        code, _ = self.run_on('src/app.py:2 "return run()"')
        self.assertEqual(code, 1)

    def test_elision_and_redacted(self):
        self.assertClean('src/app.py:3 "api_key = <redacted>"')
        self.assertClean('src/app.py:4-5 "function start […] return run"')

    def test_french_and_curly_quotes(self):
        self.assertClean("src/app.py:2 « cookie_secure »")
        self.assertClean("src/app.py:2 “cookie_secure”")

    def test_later_commit(self):
        self.assertClean('9f8e7d6:src/app.py:2 "cookie_secure: true"')
        code, _ = self.run_on('9f8e7d6:src/app.py:2 "cookie_secure: false"')
        self.assertEqual(code, 1)

    def test_workspace_copy_by_bare_name(self):
        self.assertClean('law.txt:2 "the text of the law"')
        self.assertClean('tool-output/privacy/law.txt:1 "Article 13"')

    def test_dependency_install_the_map_names(self):
        self.assertClean('node_modules/dep/index.js:1 "module"',
                         map_text="# Codebase map\ndependencies:\n  npm: installed without scripts (clone/node_modules)\n",
                         files={"clone/node_modules/dep/index.js": "module.exports = 1\n"})

    def test_not_pointers(self):
        out = self.assertClean("http://localhost:3105 and https://example.com/a/b.js:12 at 12:30, "
                               "localhost:8080, 127.0.0.1:80, vendor/...:56, F-SEC-001: ok, example.com:443")
        self.assertIn("0 pointers opened", out)

    def test_bare_name_found_nowhere_is_read_not_failed(self):
        code, out = self.run_on("helper.js:12")
        self.assertEqual(code, 0, out)
        self.assertIn("UNRESOLVED", out)

    def test_map_and_plan_open_without_quotes(self):
        self.assertClean("", plan='src/app.py:2 "the name of a fix"', map_text='src/app.py:5 "a role"')
        code, out = self.run_on("", plan="src/gone.py:2")
        self.assertEqual(code, 1)

    def test_no_findings(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_pointers.main(["check-pointers.py", tempfile.mkdtemp()]), 2)


if __name__ == "__main__":
    sys.exit(unittest.main())
