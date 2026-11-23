"""Tests for the layout of the plugins: python3 -I -m unittest discover -s <this directory>

Installing a plugin copies its directory and nothing else, so everything a
plugin's skills read or run must be inside that directory.
"""
import json
import os
import re
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"\]\(([^)\s]+)\)")
NAMESPACE = re.compile(r"/(birdiz-[a-z]+):")
ENTRY_POINTS = ("validate.py", "check-pointers.py")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def marketplace():
    return load(os.path.join(ROOT, ".claude-plugin", "marketplace.json"))["plugins"]


def plugin_root(entry):
    return os.path.normpath(os.path.join(ROOT, entry["source"]))


def files_of(top, suffix):
    for d, dirs, files in os.walk(top):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "fixtures")]
        for f in files:
            if f.endswith(suffix):
                yield os.path.join(d, f)


class TestPlugins(unittest.TestCase):
    def test_each_plugin_has_its_own_directory_and_manifest(self):
        names = [p["name"] for p in marketplace()]
        self.assertIn("birdiz-audit", names)
        self.assertEqual(len(names), len(set(names)))
        for entry in marketplace():
            with self.subTest(plugin=entry["name"]):
                root = plugin_root(entry)
                self.assertNotEqual(root, ROOT, "a plugin installed from the root copies every plugin")
                self.assertTrue(root.startswith(os.path.join(ROOT, "plugins") + os.sep), root)
                manifest = load(os.path.join(root, ".claude-plugin", "plugin.json"))
                self.assertEqual(manifest["name"], entry["name"])
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".claude-plugin", "plugin.json")),
                         "the repository root is a marketplace, not a plugin")

    def test_the_manifest_lists_every_skill_of_the_plugin(self):
        for entry in marketplace():
            with self.subTest(plugin=entry["name"]):
                root = plugin_root(entry)
                manifest = load(os.path.join(root, ".claude-plugin", "plugin.json"))
                listed = {os.path.normpath(os.path.join(root, s)) for s in manifest.get("skills", [])}
                on_disk = {os.path.dirname(p) for p in files_of(os.path.join(root, "skills"), "SKILL.md")
                           if os.path.basename(p) == "SKILL.md"}
                self.assertEqual(listed, on_disk)

    def test_links_resolve_and_skills_link_inside_their_plugin(self):
        for entry in marketplace():
            root = plugin_root(entry)
            skills = os.path.join(root, "skills") + os.sep
            for path in files_of(root, ".md"):
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                for target in LINK.findall(text):
                    if re.match(r"[a-z]+:|#|<", target):
                        continue
                    resolved = os.path.normpath(os.path.join(os.path.dirname(path), target.split("#")[0]))
                    with self.subTest(file=os.path.relpath(path, ROOT), link=target):
                        if path.startswith(skills):
                            self.assertTrue(resolved.startswith(root + os.sep), "points outside the plugin")
                        self.assertTrue(os.path.exists(resolved), "does not exist")

    def test_skills_call_commands_in_their_own_namespace(self):
        for entry in marketplace():
            for path in files_of(os.path.join(plugin_root(entry), "skills"), ".md"):
                with open(path, encoding="utf-8") as fh:
                    found = set(NAMESPACE.findall(fh.read()))
                with self.subTest(file=os.path.relpath(path, ROOT)):
                    self.assertLessEqual(found, {entry["name"]})

    def test_entry_points_import_the_plugins_copy_of_the_core(self):
        """Run as the skills run them, `python3 -I`, from another directory."""
        for entry in marketplace():
            root = plugin_root(entry)
            core = os.path.join(root, "core")
            for path in files_of(os.path.join(root, "skills"), ".py"):
                if os.path.basename(path) not in ENTRY_POINTS:
                    continue
                probe = ("import importlib.util as u, sys\n"
                         "s = u.spec_from_file_location('entry', sys.argv[1])\n"
                         "s.loader.exec_module(u.module_from_spec(s))\n"
                         "print(sys.modules['finding_core'].__file__)\n")
                done = subprocess.run([sys.executable, "-I", "-c", probe, path], cwd=os.path.dirname(ROOT),
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                with self.subTest(entry_point=os.path.relpath(path, ROOT)):
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertTrue(done.stdout.strip().startswith(core + os.sep), done.stdout)


if __name__ == "__main__":
    unittest.main()
