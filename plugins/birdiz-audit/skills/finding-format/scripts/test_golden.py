"""Golden test: the scripts' output on the synthetic workspaces under
fixtures/0.26.0/ matches, byte for byte apart from the version string, what
finding-format 0.26.0 printed. python3 -I -m unittest discover -s <this directory>

The expected files were written by the 0.26.0 scripts. Rewrite them
(`python3 -I test_golden.py --write`) only for a deliberate change of output,
and say so in the changelog.
"""
import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures", "0.26.0")
EXPECTED = os.path.join(FIXTURES, "expected")
VERSION = re.compile(r"finding-format@\d+\.\d+\.\d+(?: \(finding-core@\d+\.\d+\.\d+\))?")

CASES = [
    ("validate.py", "clean", []),
    ("validate.py", "clean", ["--require", "verification", "--require", "plan"]),
    ("validate.py", "clean", ["--fingerprint"]),
    ("validate.py", "clean", ["--fingerprint", "F-SEC-001", "F-PRI-001"]),
    ("validate.py", "flawed", []),
    ("validate.py", "flawed", ["--require", "verification", "--require", "plan"]),
    ("validate.py", "flawed", ["--fingerprint"]),
    ("validate.py", "legacy", []),
    ("validate.py", "legacy", ["--require", "plan"]),
    ("validate.py", "bare", []),
    ("validate.py", "bare", ["--require", "plan"]),
    ("check-pointers.py", "clean", []),
    ("check-pointers.py", "flawed", []),
    ("check-pointers.py", "flawed", ["--repo", "repo"]),
    ("check-pointers.py", "legacy", []),
    ("check-pointers.py", "bare", []),
]


def load(script):
    spec = importlib.util.spec_from_file_location(script[:-3].replace("-", "_"), os.path.join(HERE, script))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def name_of(script, workspace, args):
    tail = "-".join(a.lstrip("-") for a in args)
    return "%s.%s%s.txt" % (script[:-3], workspace, "." + tail if tail else "")


def run(module, script, workspace, args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = module.main([script, os.path.join(FIXTURES, workspace)] + args)
    return "%s# exit %d\n" % (out.getvalue(), code)


class GoldenTest(unittest.TestCase):
    def test_output_matches_0_26_0(self):
        modules = {}
        for script, workspace, args in CASES:
            module = modules.setdefault(script, load(script))
            with self.subTest(script=script, workspace=workspace, args=" ".join(args)):
                with open(os.path.join(EXPECTED, name_of(script, workspace, args)), encoding="utf-8") as fh:
                    expected = fh.read()
                actual = run(module, script, workspace, args)
                self.assertEqual(VERSION.sub("<version>", actual), VERSION.sub("<version>", expected))

    def test_entry_points_run_isolated(self):
        """`python3 -I` puts no script directory on the path from 3.11 on: each
        entry point finds the core and its extension itself."""
        for script in ("validate.py", "check-pointers.py"):
            with self.subTest(script=script):
                done = subprocess.run([sys.executable, "-I", os.path.join(HERE, script), "--version"],
                                      cwd=os.path.dirname(HERE), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      universal_newlines=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertRegex(done.stdout, VERSION)


def write():
    os.makedirs(EXPECTED, exist_ok=True)
    modules = {}
    for script, workspace, args in CASES:
        module = modules.setdefault(script, load(script))
        with open(os.path.join(EXPECTED, name_of(script, workspace, args)), "w", encoding="utf-8") as fh:
            fh.write(run(module, script, workspace, args))


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write()
    else:
        unittest.main()
