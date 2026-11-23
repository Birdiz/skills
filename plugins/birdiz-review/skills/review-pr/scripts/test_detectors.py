"""Tests for the stack-agnostic detectors, files in and files out:
python3 -I -m unittest discover -s <this directory>

Each test builds a tiny git repository with a base on `main` and a head on
`feature/x`, runs run.py on it as the skill does, and reads the detector
outputs under `signals/`, the contracts worksheet and the brief. The paths
backed by squawk and oasdiff run against fake tools that print what the
real ones print, and against the real tools only when they are installed;
the heuristic paths always run.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_run import GIT, Fixture, check, entry, git, read, write  # noqa: E402

SQUAWK = shutil.which("squawk")
OASDIFF = shutil.which("oasdiff")


class Repo(Fixture):
    """A repository whose base and head are given as {path: text}; a head
    value of None deletes the file. Bytes are written as they are."""

    def __init__(self, test, base, head):  # noqa: super().__init__ builds another repository
        self.tmp = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.tmp)
        self.repo = os.path.join(self.tmp, "shop")
        self.state = os.path.join(self.tmp, "state")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.repo)
        os.makedirs(self.bin)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        self.put(base)
        git(self.repo, "add", "-A")
        self.base = git(self.repo, "commit", "-qm", "base", "--allow-empty")
        git(self.repo, "checkout", "-qb", "feature/x")
        self.put(head)
        git(self.repo, "add", "-A")
        self.head = git(self.repo, "commit", "-qm", "head")
        git(self.repo, "checkout", "-q", "main")

    def put(self, files):
        for rel, text in files.items():
            path = os.path.join(self.repo, rel)
            if text is None:
                os.remove(path)
            elif isinstance(text, bytes):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(text)
            else:
                write(self.repo, rel, text)

    def script(self, name, body):
        """A fake tool: a Python script first on the PATH."""
        path = os.path.join(self.bin, name)
        write(self.bin, name, "#!%s -I\nimport sys\n%s" % (sys.executable, body))
        os.chmod(path, 0o755)


@unittest.skipIf(GIT is None, "git is not installed")
class DetectorCase(unittest.TestCase):
    def start(self, base, head, tools=()):
        self.fx = Repo(self, base, head)
        for name, body in tools:
            self.fx.script(name, body)
        code, root, out = self.fx.run("feature/x")
        self.assertEqual(code, 0, out)
        self.root = root
        return root

    def output(self, name):
        return json.loads(read(os.path.join(self.root, "signals", name + ".json")))

    def kinds(self, name):
        return [(s["path"], s["kind"], s.get("line")) for s in self.output(name)["signals"]]

    def brief(self):
        return read(os.path.join(self.root, "brief.md"))

    def assertValid(self):
        code, report = check(self.root, "--require", "brief")
        self.assertEqual(code, 0, report)
        self.assertEqual(entry("check-pointers.py", self.root)[0], 0, "the worksheet's pointers open")


class TestMigrations(DetectorCase):
    def test_a_dropped_column(self):
        self.start({"db/migrations/001_users.sql": "CREATE TABLE users (id int, email text);\n"},
                   {"db/migrations/002_drop_email.sql": "-- drop it\nALTER TABLE users DROP COLUMN email;\n"})
        out = self.output("migrations")
        self.assertTrue(out["content"])
        self.assertEqual(out["covered"], ["db/migrations/002_drop_email.sql"])
        self.assertEqual(self.kinds("migrations"), [("db/migrations/002_drop_email.sql", "drop", 2)])
        self.assertEqual(out["signals"][0]["excerpt"], "ALTER TABLE users DROP COLUMN email;")
        if not SQUAWK:
            self.assertEqual(out["tool"], None)
            self.assertIn("squawk not found on this machine: raw SQL migrations read by the heuristic only",
                          out["gaps"])
            self.assertIn("- signals/migrations.json: squawk not found on this machine", self.brief())
        sheet = read(os.path.join(self.root, "findings", "contracts.md"))
        self.assertIn("| S1 `db/migrations/002_drop_email.sql:2` migrations `drop`: drops a table, a column or"
                      " another object, or empties a table | ? | |", sheet)
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `db/migrations/002_drop_email.sql`: added (signals/git-changes.json); drops a table", glance)
        self.assertValid()

    def test_destructive_statements_renames_not_null_and_an_edited_migration(self):
        self.start({"migrations/001.sql": "CREATE TABLE a (id int);\n"},
                   {"migrations/001.sql": "CREATE TABLE a (id bigint);\n",
                    "migrations/002.sql": "ALTER TABLE a RENAME COLUMN id TO key;\n"
                                          "ALTER TABLE a ADD COLUMN owner text NOT NULL;\n"
                                          "ALTER TABLE a ADD COLUMN note text NOT NULL DEFAULT '';\n"
                                          "ALTER TABLE a ALTER COLUMN key SET NOT NULL;\n"
                                          "DELETE FROM a;\n",
                    "migrations/003.up.sql": "TRUNCATE a;\n"})
        self.assertEqual(self.kinds("migrations"), [
            ("migrations/001.sql", "migration-edited", 1),
            ("migrations/002.sql", "rename", 1), ("migrations/002.sql", "not-null", 2),
            ("migrations/002.sql", "not-null", 4), ("migrations/002.sql", "data-rewrite", 5),
            ("migrations/003.up.sql", "drop", 1), ("migrations/003.up.sql", "no-down", 1)])

    def test_framework_migrations_are_read_as_code_by_the_step(self):
        self.start({"app.py": "x = 1\n"}, {
            "database/migrations/2026_11_01_000000_drop_email.php":
                "<?php\nreturn new class extends Migration {\n    public function up(): void\n    {\n"
                "        Schema::table('users', function (Blueprint $t) { $t->dropColumn('email'); });\n    }\n};\n",
            "alembic/versions/a1_rename.py":
                "def upgrade():\n    op.rename_table('a', 'b')\n\n\ndef downgrade():\n    pass\n",
            "shop/migrations/0002_remove_email.py":
                "operations = [migrations.RemoveField(model_name='user', name='email'), RunSQL('x')]\n"})
        kinds = self.kinds("migrations")
        for item in (("database/migrations/2026_11_01_000000_drop_email.php", "framework-migration", 1),
                     ("database/migrations/2026_11_01_000000_drop_email.php", "drop", 5),
                     ("database/migrations/2026_11_01_000000_drop_email.php", "no-down", 1),
                     ("alembic/versions/a1_rename.py", "framework-migration", 1),
                     ("alembic/versions/a1_rename.py", "rename", 2),
                     ("alembic/versions/a1_rename.py", "no-down", 1),
                     ("shop/migrations/0002_remove_email.py", "framework-migration", 1),
                     ("shop/migrations/0002_remove_email.py", "drop", 1),
                     ("shop/migrations/0002_remove_email.py", "no-down", 1)):
            self.assertIn(item, kinds)
        reasons = {s["kind"]: s["reason"] for s in self.output("migrations")["signals"]
                   if s["path"].startswith("alembic")}
        self.assertEqual(reasons["no-down"], "no way back: `downgrade()` does nothing")
        self.assertIn("Alembic migration: its SQL is not generated in this version, the contracts step reads it"
                      " as code", reasons["framework-migration"])
        self.assertNotIn("app.py", self.output("migrations")["covered"])

    def test_a_file_a_detector_could_not_read_is_unproven(self):
        self.start({"x.txt": "x\n"}, {"migrations/004.sql": b"\x00\x01binary"})
        out = self.output("migrations")
        self.assertEqual(out["not_covered"], [{"path": "migrations/004.sql", "reason": "binary or not UTF-8 text"}])
        unproven = self.brief().split("## Unproven")[1].split("## ")[0]
        self.assertIn("- `migrations/004.sql`: signals/migrations.json applies but did not cover it: binary or not"
                      " UTF-8 text.", unproven)
        self.assertValid()

    def test_raw_sql_goes_through_a_fake_squawk(self):
        fake = ('if "--version" in sys.argv:\n    print("squawk 1.4.2")\n    sys.exit(0)\n'
                'for f in sys.argv[1:]:\n    if f.endswith(".sql"):\n'
                '        print(f + ":1:0: warning: ban-drop-column Dropping a column may break existing clients.")\n'
                'sys.exit(1)\n')
        self.start({"x.txt": "x\n"}, {"db/migrations/002.sql": "ALTER TABLE users DROP COLUMN email;\n"},
                   tools=[("squawk", fake)])
        out = self.output("migrations")
        self.assertEqual(out["tool"], "squawk@1.4.2")
        self.assertEqual(out["gaps"], [])
        self.assertIn(("db/migrations/002.sql", "squawk:ban-drop-column", 1), self.kinds("migrations"))
        self.assertIn(("db/migrations/002.sql", "drop", 1), self.kinds("migrations"), "the heuristic still runs")
        self.assertIn("signals/migrations.json (squawk@1.4.2)", self.brief())

    @unittest.skipIf(SQUAWK is None, "squawk is not installed")
    def test_raw_sql_goes_through_squawk(self):
        self.start({"x.txt": "x\n"}, {"db/migrations/002.sql": "ALTER TABLE users DROP COLUMN email;\n"})
        out = self.output("migrations")
        self.assertTrue(out["tool"].startswith("squawk@"), out)
        self.assertTrue(any(k.startswith("squawk:") for _, k, _ in self.kinds("migrations")), out)


class TestConfig(DetectorCase):
    def test_a_new_required_env_var(self):
        self.start({"settings.py": "DEBUG = False\n", ".env.example": "APP_NAME=shop\nOLD_FLAG=1\n", "src/pay.py": "import os\nHOME = os.environ['HOME_DIR']\n",
                    "config/app.php": "<?php\nreturn ['name' => env('APP_NAME', 'shop'), 'debug' => true];\n"},
                   {"settings.py": "DEBUG = False\nCACHE_TTL = 0\n", ".env.example": "APP_NAME=store\nSTRIPE_KEY=\n",
                    "src/pay.py": "import os\nHOME = os.environ['HOME_DIR']\nKEY = os.environ['STRIPE_KEY']\n"
                                  "OPT = os.environ.get('OPTIONAL_X', 'x')\n",
                    "config/app.php": "<?php\nreturn ['name' => env('APP_NAME', 'shop'), 'mail' => env('MAIL_HOST')];\n"})
        self.assertEqual(sorted(self.kinds("config")), sorted([
            (".env.example", "env-default-changed", 1), (".env.example", "env-added", 2),
            (".env.example", "env-removed", None),
            ("src/pay.py", "env-required", 3),
            ("config/app.php", "env-required", 2), ("config/app.php", "config-changed", 2),
            ("settings.py", "config-added", 2)]))
        reasons = {(s["path"], s["kind"]): s["reason"] for s in self.output("config")["signals"]}
        self.assertEqual(reasons[(".env.example", "env-added")], "new variable `STRIPE_KEY` with no default value")
        self.assertEqual(reasons[("src/pay.py", "env-required")],
                         "reads environment variable `STRIPE_KEY` with no default, mentioned nowhere at the base")
        out = self.output("config")
        self.assertEqual(sorted(out["covered"]), [".env.example", "config/app.php", "settings.py"])
        self.assertNotIn("src/pay.py", out["covered"], "a code file is scanned for variables, not covered")
        unproven = self.brief().split("## Unproven")[1].split("## ")[0]
        self.assertIn("- `src/pay.py`: no content detector reads this file type", unproven)
        self.assertValid()


class TestRoutesAndContracts(DetectorCase):
    def test_removed_and_changed_routes(self):
        self.start({"routes/web.php": "<?php\nRoute::get('/old', [A::class, 'x']);\nRoute::get('/keep', [A::class, 'y']);\n",
                    "shop/urls.py": "urlpatterns = [\n    path('cart/', views.cart),\n]\n",
                    "app/api.py": "@app.get('/ping')\ndef ping():\n    return 1\n"},
                   {"routes/web.php": "<?php\nRoute::get('/keep', [A::class, 'y']);\n\n\n\nRoute::post('/new', [A::class, 'z']);\n",
                    "shop/urls.py": "urlpatterns = [\n    path('basket/', views.cart),\n]\n",
                    "app/api.py": "def ping():\n    return 1\n"})
        self.assertEqual(sorted(self.kinds("routes")), sorted([
            ("routes/web.php", "route-removed", 2), ("routes/web.php", "route-added", 6),
            ("shop/urls.py", "route-changed", 2),
            ("app/api.py", "route-removed", 1)]))
        self.assertEqual(sorted(self.output("routes")["covered"]), ["routes/web.php", "shop/urls.py"])
        self.assertValid()

    def test_openapi_and_graphql_by_the_heuristic(self):
        spec = ("openapi: 3.0.0\ninfo:\n  title: shop\npaths:\n  /pets:\n    get:\n      summary: list\n"
                "    post:\n      summary: add\n  /users:\n    get:\n      summary: users\n")
        self.start({"api/openapi.yaml": spec, "schema.graphql": "type User {\n  id: ID!\n  email: String\n}\n"},
                   {"api/openapi.yaml": "openapi: 3.0.0\ninfo:\n  title: shop\npaths:\n  /pets:\n    get:\n"
                                        "      summary: list\n",
                    "schema.graphql": "type User {\n  id: ID!\n}\n"})
        kinds = self.kinds("api-contracts")
        self.assertIn(("api/openapi.yaml", "path-removed", None), kinds)
        self.assertIn(("api/openapi.yaml", "operation-removed", None), kinds)
        self.assertIn(("api/openapi.yaml", "contract-changed", 7), kinds)
        self.assertIn(("schema.graphql", "field-removed", 3), kinds)
        out = self.output("api-contracts")
        if not OASDIFF:
            self.assertTrue(out["heuristic"])
            self.assertIn("oasdiff not found on this machine: OpenAPI files read by the heuristic only", out["gaps"])
        self.assertValid()

    def test_an_openapi_file_is_found_by_its_content(self):
        self.start({"docs/api.json": json.dumps({"openapi": "3.0.0", "paths": {"/a": {"get": {}, "put": {}}}})},
                   {"docs/api.json": json.dumps({"openapi": "3.0.0", "paths": {"/a": {"get": {}}}})})
        self.assertIn(("docs/api.json", "operation-removed", None), self.kinds("api-contracts"))
        self.assertEqual(self.output("api-contracts")["applies_to"], ["docs/api.json"])

    def test_openapi_goes_through_a_fake_oasdiff(self):
        fake = ('import json\nif "--version" in sys.argv:\n    print("oasdiff version v1.10.3")\n    sys.exit(0)\n'
                'assert sys.argv[1] == "breaking" and "--format" in sys.argv\n'
                'print(json.dumps([{"id": "api-path-removed-without-deprecation", "text": "api path removed without'
                ' deprecation", "level": 3, "operation": "GET", "path": "/users"}]))\n')
        self.start({"openapi.yaml": "openapi: 3.0.0\npaths:\n  /users:\n    get: {}\n"},
                   {"openapi.yaml": "openapi: 3.0.0\npaths: {}\n"}, tools=[("oasdiff", fake)])
        out = self.output("api-contracts")
        self.assertEqual((out["tool"], out["heuristic"], out["gaps"]), ("oasdiff@1.10.3", False, []))
        self.assertEqual(out["signals"], [{"path": "openapi.yaml", "kind": "oasdiff:api-path-removed-without-deprecation",
                                           "reason": "`GET /users`: api path removed without deprecation (error)"}])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".tool-trees")), "the base side is removed")

    @unittest.skipIf(OASDIFF is None, "oasdiff is not installed")
    def test_openapi_goes_through_oasdiff(self):
        self.start({"openapi.yaml": "openapi: 3.0.0\ninfo:\n  title: a\n  version: '1'\npaths:\n  /users:\n"
                                    "    get:\n      responses:\n        '200':\n          description: ok\n"},
                   {"openapi.yaml": "openapi: 3.0.0\ninfo:\n  title: a\n  version: '1'\npaths: {}\n"})
        out = self.output("api-contracts")
        self.assertTrue(out["tool"].startswith("oasdiff@"), out)
        self.assertTrue(any(k.startswith("oasdiff:") for _, k, _ in self.kinds("api-contracts")), out)


class TestDependencies(DetectorCase):
    def test_a_new_dependency(self):
        self.start({"package.json": json.dumps({"dependencies": {"left-pad": "^1.0.0"}, "engines": {"node": ">=18"}},
                                               indent=2),
                    "package-lock.json": "{}\n", "requirements.txt": "requests==2.31\nflask>=3\n",
                    "composer.json": json.dumps({"require": {"php": ">=8.1"}}), "composer.lock": "{}\n",
                    "web/package.json": "{}\n", "web/yarn.lock": "a@1\n"},
                   {"package.json": json.dumps({"dependencies": {"left-pad": "^2.0.0", "axios": "^1.6.0"},
                                                "engines": {"node": ">=20"}}, indent=2),
                    "package-lock.json": "{\"x\": 1}\n", "requirements.txt": "flask>=3\n",
                    "composer.json": json.dumps({"require": {"php": ">=8.1"}, "scripts": {"post-install-cmd": "x"}}),
                    "composer.lock": "{\"y\": 1}\n", "web/yarn.lock": "a@2\n"})
        kinds = self.kinds("dependencies")
        self.assertIn(("package.json", "dependency-added", 4), kinds)
        self.assertIn(("package.json", "dependency-changed", 3), kinds)
        self.assertIn(("package.json", "runtime-changed", 7), kinds)
        self.assertIn(("requirements.txt", "dependency-removed", None), kinds)
        reasons = {(s["path"], s["kind"]): s["reason"] for s in self.output("dependencies")["signals"]}
        self.assertEqual(reasons[("package.json", "dependency-added")], "new dependency `axios` ^1.6.0 (dependencies)")
        self.assertIn("a new major version", reasons[("package.json", "dependency-changed")])
        self.assertIn("with its manifest `package.json`", reasons[("package-lock.json", "lockfile-changed")])
        self.assertIn("with its manifest `composer.json`", reasons[("composer.lock", "lockfile-changed")])
        self.assertIn(("composer.json", "manifest-changed", 1), kinds, "a scripts change is not skim")
        self.assertIn("without its manifest `web/package.json` changing", reasons[("web/yarn.lock", "lockfile-changed")])
        self.assertValid()

    def test_an_unreadable_manifest_is_not_covered(self):
        self.start({"package.json": "{}\n"}, {"package.json": "{not json\n"})
        out = self.output("dependencies")
        self.assertEqual(out["covered"], [])
        self.assertTrue(out["not_covered"][0]["reason"].startswith("not valid JSON"))


class TestAssertions(DetectorCase):
    def test_an_edited_assertion(self):
        base = ("from app import greet\n\n\ndef test_greet():\n    assert greet('a') == 'hello a'\n\n\n"
                "def test_other():\n    x = 1\n    assert x == 1\n")
        self.start({"tests/test_app.py": base, "tests/test_gone.py": "def test_x():\n    assert True\n"},
                   {"tests/test_app.py": ("import pytest\nfrom app import greet\n\n\ndef test_greet():\n"
                                          "    assert greet('a') == 'hello a!'\n\n\n@pytest.mark.skip\n"
                                          "def test_other():\n    x = 2\n"),
                    "tests/test_gone.py": None})
        kinds = self.kinds("assertions")
        self.assertIn(("tests/test_app.py", "assertion-modified", 6), kinds)
        self.assertIn(("tests/test_app.py", "skip-added", 9), kinds)
        self.assertIn(("tests/test_app.py", "assertion-removed", 11), kinds)
        self.assertIn(("tests/test_gone.py", "test-deleted", None), kinds)
        mod = next(s for s in self.output("assertions")["signals"] if s["kind"] == "assertion-modified")
        self.assertEqual(mod["excerpt"], "assert greet('a') == 'hello a'", "the excerpt is the assertion as it was")
        self.assertValid()

    def test_a_test_file_that_only_gains_assertions_is_skim(self):
        self.start({"tests/test_app.py": "def test_a():\n    assert 1\n"},
                   {"tests/test_app.py": "def test_a():\n    assert 1\n\n\ndef test_b():\n    assert 2\n"})
        self.assertEqual(self.kinds("assertions"), [])
        skim = self.brief().split("## Skim")[1].split("## ")[0]
        self.assertIn("- `tests/test_app.py`: covered by signals/assertions.json, with no signal; no finding points"
                      " at it; outside the risk map.", skim)
        self.assertValid()


class TestFanIn(DetectorCase):
    def test_changed_and_removed_public_symbols_count_their_references_outside_the_diff(self):
        self.start({"src/lib.py": "def compute_total(a):\n    return a\n\n\ndef legacy_helper():\n    return 0\n",
                    "src/other.py": "from lib import compute_total\n\nprint(compute_total(1))\n",
                    "src/third.py": "# legacy_helper is mentioned in a comment only\nfrom lib import legacy_helper\n"},
                   {"src/lib.py": "def compute_total(a, b):\n    return a + b\n"})
        out = self.output("fan-in")
        self.assertFalse(out["content"])
        symbols = {s["symbol"]: s for s in out["symbols"]}
        self.assertEqual((symbols["compute_total"]["change"], symbols["compute_total"]["fan_in"]), ("signature", 2))
        self.assertEqual(symbols["compute_total"]["refs"], ["src/other.py:1", "src/other.py:3"])
        self.assertEqual((symbols["legacy_helper"]["change"], symbols["legacy_helper"]["fan_in"]), ("removed", 1),
                         "a comment is not a reference")
        self.assertEqual(sorted(self.kinds("fan-in")), [("src/lib.py", "symbol-removed", None),
                                                          ("src/lib.py", "symbol-signature", 1)])
        declared = self.brief().split("## Declared vs detected")[1].split("## ")[0]
        self.assertIn("fan-in (heuristic): `compute_total` in `src/lib.py` 2 (signature), `legacy_helper` in"
                      " `src/lib.py` 1 (removed)", declared)
        self.assertValid()


if __name__ == "__main__":
    unittest.main()
