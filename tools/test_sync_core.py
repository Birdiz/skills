"""Tests for sync_core.py: python3 -I -m unittest discover -s <this directory>"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("sync_core", os.path.join(HERE, "sync_core.py"))
sync_core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_core)


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = sync_core.main(["sync_core.py"] + list(args))
    return code, out.getvalue()


class Repo:
    """A throwaway repository: a marketplace, a core and the plugins named."""

    def __init__(self, test, sources=("plugins/one", "plugins/two")):
        self.root = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.root)
        self.write("core/finding_core/__init__.py", 'VERSION = "0.1.0"\n')
        self.write("core/finding_core/validator.py", "def main():\n    return 0\n")
        plugins = []
        for source in sources:
            os.makedirs(os.path.join(self.root, source), exist_ok=True)
            plugins.append({"name": os.path.basename(source), "source": "./" + source})
        self.write(".claude-plugin/marketplace.json", json.dumps({"name": "test", "plugins": plugins}))

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as fh:
            return fh.read()

    def check(self):
        return run("--check", "--root", self.root)

    def sync(self):
        return run("--root", self.root)


class TestSyncCore(unittest.TestCase):
    def test_this_repository_is_in_sync(self):
        code, out = run("--check")
        self.assertEqual(code, 0, out)

    def test_sync_copies_the_core_into_every_plugin(self):
        repo = Repo(self)
        self.assertEqual(repo.check()[0], 1)
        code, out = repo.sync()
        self.assertEqual(code, 0, out)
        for plugin in ("plugins/one", "plugins/two"):
            self.assertEqual(repo.read(plugin + "/core/finding_core/validator.py"),
                             repo.read("core/finding_core/validator.py"))
        code, out = repo.check()
        self.assertEqual(code, 0, out)
        self.assertIn("in sync in 2 plugin(s)", out)

    def test_check_fails_when_a_copy_is_edited(self):
        repo = Repo(self)
        repo.sync()
        repo.write("plugins/two/core/finding_core/validator.py", "def main():\n    return 1\n")
        code, out = repo.check()
        self.assertEqual(code, 1, out)
        self.assertIn("DRIFT    plugins/two/core/finding_core/validator.py: differs from the source", out)
        self.assertNotIn("plugins/one", out.replace("in sync", ""))

    def test_check_fails_when_the_source_changes_and_no_sync_follows(self):
        repo = Repo(self)
        repo.sync()
        repo.write("core/finding_core/validator.py", "def main():\n    return 2\n")
        code, out = repo.check()
        self.assertEqual(code, 1, out)
        self.assertIn("plugins/one/core/finding_core/validator.py: differs", out)
        self.assertIn("plugins/two/core/finding_core/validator.py: differs", out)

    def test_check_fails_on_a_missing_or_an_extra_file(self):
        repo = Repo(self)
        repo.sync()
        os.remove(repo.path("plugins/one/core/finding_core/__init__.py"))
        repo.write("plugins/one/core/finding_core/local.py", "x = 1\n")
        code, out = repo.check()
        self.assertEqual(code, 1, out)
        self.assertIn("plugins/one/core/finding_core/__init__.py: missing", out)
        self.assertIn("plugins/one/core/finding_core/local.py: not in the source", out)

    def test_sync_repairs_drift_and_removes_extra_files(self):
        repo = Repo(self)
        repo.sync()
        repo.write("plugins/one/core/finding_core/validator.py", "edited\n")
        repo.write("plugins/one/core/stale/old.py", "x = 1\n")
        code, out = repo.sync()
        self.assertEqual(code, 0, out)
        self.assertEqual(repo.check()[0], 0)
        self.assertFalse(os.path.exists(repo.path("plugins/one/core/stale")))

    def test_caches_are_not_drift(self):
        repo = Repo(self)
        repo.sync()
        repo.write("plugins/one/core/finding_core/__pycache__/validator.cpython-313.pyc", "")
        repo.write("plugins/one/core/.DS_Store", "")
        self.assertEqual(repo.check()[0], 0)

    def test_a_plugin_at_the_repository_root_is_refused(self):
        repo = Repo(self, sources=())
        repo.write(".claude-plugin/marketplace.json",
                   json.dumps({"name": "test", "plugins": [{"name": "all", "source": "./"}]}))
        code, out = repo.check()
        self.assertEqual(code, 2, out)
        self.assertIn("must be its own directory", out)

    def test_an_unreadable_marketplace_cannot_be_checked(self):
        repo = Repo(self)
        os.remove(repo.path(".claude-plugin/marketplace.json"))
        self.assertEqual(repo.check()[0], 2)


if __name__ == "__main__":
    unittest.main()
