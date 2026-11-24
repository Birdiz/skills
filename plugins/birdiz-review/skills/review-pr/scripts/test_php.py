"""Tests for the PHP adapter, files in and files out:
python3 -I -m unittest discover -s <this directory>

Each repository test builds a tiny PHP repository with a base on `main` and
a head on `feature/x`, runs run.py on it as the skill does, and reads the
detector outputs, the contracts worksheet and the brief. The deptrac path
runs against a fake tool that prints what the real one prints, and Roave's
BC check against a fake that fails the test if it is ever run on a tree.
The parser tests read PHP text directly, for what the lexer must not be
fooled by.
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
import php  # noqa: E402
from test_detectors import DetectorCase  # noqa: E402
from test_run import read  # noqa: E402

COMPOSER = json.dumps({"autoload": {"psr-4": {"App\\": "src/"}}, "autoload-dev": {"psr-4": {"Tests\\": "tests/"}}})
INVOICE = ("<?php\n\nnamespace App\\Billing;\n\nuse App\\Billing\\Line;\n\nclass Invoice\n{\n"
           "    public function total(): int\n    {\n        return 1;\n    }\n\n"
           "    private function secret(): int\n    {\n        return 2;\n    }\n}\n")
CHECKOUT = ("<?php\n\nnamespace App\\Shop;\n\nuse App\\Billing\\Invoice;\n\nfinal class Checkout\n{\n"
            "    public function pay(Invoice $invoice): int\n    {\n        // $invoice->total() in a comment is no call\n"
            "        return $invoice->total() + $invoice->total();\n    }\n}\n")


class TestPublicApi(DetectorCase):
    def test_a_renamed_public_method(self):
        self.start({"composer.json": COMPOSER, "src/Billing/Invoice.php": INVOICE, "src/Shop/Checkout.php": CHECKOUT},
                   {"src/Billing/Invoice.php": INVOICE.replace("function total()", "function grandTotal()")})
        out = self.output("public-api")
        self.assertEqual((out["content"], out["heuristic"], out["tool"]), (True, True, None))
        self.assertEqual(out["covered"], ["src/Billing/Invoice.php"])
        self.assertEqual(self.kinds("public-api"), [("src/Billing/Invoice.php", "method-removed", 9)])
        self.assertEqual(out["signals"][0]["reason"], "public method `Invoice::total()` removed;"
                         " `Invoice::grandTotal()` appears in its place, a rename")
        self.assertTrue(any(g.startswith("roave-backward-compatibility-check not run (not found on this machine): it"
                                         " runs `composer install`") for g in out["gaps"]), out["gaps"])
        symbols = {s["symbol"]: s for s in self.output("fan-in")["symbols"]}
        self.assertEqual((symbols["Invoice::total"]["change"], symbols["Invoice::total"]["fan_in"]), ("removed", 2))
        self.assertEqual(symbols["Invoice::total"]["refs"], ["src/Shop/Checkout.php:12", "src/Shop/Checkout.php:12"],
                         "a comment is not a reference")
        self.assertEqual(self.kinds("fan-in"), [], "the public API diff signals the break, fan-in only counts")
        sheet = read(os.path.join(self.root, "findings", "contracts.md"))
        self.assertIn("| S1 `src/Billing/Invoice.php:9` public-api `method-removed`: public method `Invoice::total()`"
                      " removed;", sheet)
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `src/Billing/Invoice.php`: public method `Invoice::total()` removed", glance)
        self.assertIn("fan-in (heuristic): `Invoice::total` in `src/Billing/Invoice.php` 2 (removed)", self.brief())
        self.assertValid()

    def test_signature_changes_visibility_and_interfaces(self):
        base = ("<?php\nnamespace App\\Billing;\n\nuse App\\Money\\Amount;\n\ninterface Payable\n{\n"
                "    public function pay(Amount $a): void;\n}\n\nclass Account implements Payable\n{\n"
                "    public const LIMIT = 10;\n    public ?string $owner = null;\n\n"
                "    public function pay(Amount $a): void {}\n    public function open(string $who, int $days = 3): bool"
                " { return true; }\n    public function close() {}\n    /** @internal */\n"
                "    public function debug(): void {}\n}\n")
        head = ("<?php\nnamespace App\\Billing;\n\nuse App\\Money\\Amount;\nuse App\\Money\\Amount as Sum;\n\n"
                "interface Payable\n{\n    public function pay(Sum $a): void;\n    public function refund(): void;\n}\n\n"
                "final class Account implements Payable\n{\n    public int $owner = 0;\n\n"
                "    public function pay(Amount $a): void {}\n    public function refund(): void {}\n"
                "    public function open(string $name, int $days, bool $now): bool { return true; }\n"
                "    protected function close() {}\n}\n")
        self.start({"src/Billing/Account.php": base}, {"src/Billing/Account.php": head})
        reasons = {(k, r) for _, k, r in [(s["path"], s["kind"], s["reason"]) for s in self.output("public-api")["signals"]]}
        self.assertEqual(reasons, {
            ("interface-method-added", "interface method `Payable::refund()` added: implementations outside the diff"
                                       " must define it"),
            ("class-changed", "class `App\\Billing\\Account` became final: subclasses outside the diff break"),
            ("signature-changed", "public method `Account::open()`: parameter `$who` renamed `$name`: named arguments"
                                  " break; `$days` lost its default: calls that omit it break; new required parameter"
                                  " `$now`"),
            ("visibility-reduced", "method `Account::close()` public -> protected"),
            ("constant-removed", "constant `Account::LIMIT` removed"),
            ("property-changed", "property `Account::$owner`: type ?string -> int"),
        }, "an alias of the same class is no change, and an @internal method is not API")

    def test_fan_in_counts_constructor_calls_and_leaves_new_methods_out(self):
        base = INVOICE.replace("class Invoice\n{\n", "class Invoice\n{\n    public function __construct(int $a) {}\n\n")
        head = base.replace("__construct(int $a)", "__construct(int $a, int $b)").replace(
            "    private function secret", "    public function discount(): int\n    {\n        return 0;\n    }\n\n"
            "    private function secret")
        self.start({"composer.json": COMPOSER, "src/Billing/Invoice.php": base,
                    "src/Shop/Cart.php": "<?php\nnamespace App\\Shop;\nuse App\\Billing\\Invoice;\n"
                                         "class Cart extends Base\n{\n    public function __construct() { parent::__construct(); }\n"
                                         "    public function bill(): Invoice { return new Invoice(1); }\n}\n"},
                   {"src/Billing/Invoice.php": head})
        symbols = {s["symbol"]: s for s in self.output("fan-in")["symbols"]}
        self.assertEqual(sorted(symbols), ["Invoice::__construct"], "a method new in the diff has no caller to count")
        self.assertEqual((symbols["Invoice::__construct"]["change"], symbols["Invoice::__construct"]["fan_in"],
                          symbols["Invoice::__construct"]["refs"]), ("signature", 1, ["src/Shop/Cart.php:7"]))

    def test_a_php_file_with_no_signal_is_skim(self):
        self.start({"composer.json": COMPOSER, "src/Billing/Invoice.php": INVOICE},
                   {"src/Billing/Invoice.php": INVOICE.replace("return 1;", "return 1 + 0;")})
        self.assertEqual(self.kinds("public-api") + self.kinds("import-graph-php"), [])
        self.assertEqual(self.output("fan-in")["symbols"][0]["change"], "body")
        skim = self.brief().split("## Skim")[1].split("## ")[0]
        self.assertIn("- `src/Billing/Invoice.php`: covered by signals/import-graph-php.json, signals/public-api.json, with no"
                      " signal; no finding points at it; outside the risk map.", skim)
        self.assertValid()

    def test_in_the_risk_map_it_is_glance_and_never_skim(self):
        review = ("# Review\n\n## Stacks\n\n- php\n\n## Risk map\n\n| Glob | Zone |\n|---|---|\n"
                  "| `src/Billing/**` | payments |\n")
        self.start({"composer.json": COMPOSER, "src/Billing/Invoice.php": INVOICE, "docs/agents/review.md": review},
                   {"src/Billing/Invoice.php": INVOICE.replace("return 1;", "return 1 + 0;")})
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `src/Billing/Invoice.php`: risk zone payments (`src/Billing/**`)", glance)
        self.assertValid()

    def test_templates_and_unreadable_php_are_unproven(self):
        self.start({"x.txt": "x\n"}, {"resources/views/home.blade.php": "<h1>{{ $title }}</h1>\n",
                                      "public/page.php": "<html>no open tag</html>\n",
                                      "src/Broken.php": "<?php\nclass Broken {\n    public function x() {\n"})
        out = self.output("public-api")
        self.assertNotIn("resources/views/home.blade.php", out["applies_to"])
        self.assertEqual(sorted((i["path"], i["reason"]) for i in out["not_covered"]), [
            ("public/page.php", "not readable as PHP at the head: no `<?php` tag: a template, not code"),
            ("src/Broken.php", "not readable as PHP at the head: a `{` never closes")])
        unproven = self.brief().split("## Unproven")[1].split("## ")[0]
        self.assertIn("- `resources/views/home.blade.php`: no content detector reads this file type", unproven)
        self.assertIn("- `src/Broken.php`: signals/import-graph-php.json applies but did not cover it", unproven)
        self.assertValid()

    def test_roave_is_never_run_on_a_tree(self):
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch)
        marker = os.path.join(scratch, "roave-ran")
        fake = ('if sys.argv[1:] == ["--version"]:\n    print("Roave BC check 8.27.0")\n    sys.exit(0)\n'
                'open(%r, "w").write(" ".join(sys.argv))\nsys.exit(3)\n' % marker)
        self.start({"src/A.php": "<?php\nclass A { public function run() {} }\n"},
                   {"src/A.php": "<?php\nclass A { }\n"}, tools=[("roave-backward-compatibility-check", fake)])
        self.assertFalse(os.path.exists(marker), "Roave's BC check was run")
        tools = {t["name"]: t for t in json.loads(read(os.path.join(self.root, "run.json")))["tools"]}
        roave = tools["roave-backward-compatibility-check"]
        self.assertEqual((roave["found"], roave["needs"], roave["installs"], roave["allowed"]),
                         (True, "dependencies", True, False))
        self.assertEqual((tools["deptrac"]["needs"], tools["deptrac"]["allowed"]), ("nothing", True))
        self.assertTrue(self.output("public-api")["gaps"][0].startswith(
            "roave-backward-compatibility-check not run (found on this machine)"))
        self.assertIn("- signals/public-api.json: roave-backward-compatibility-check not run", self.brief())


class TestImports(DetectorCase):
    CARRIER = ("<?php\n\nnamespace App\\Shipping;\n\nuse App\\Billing\\Invoice;\n\nclass Carrier\n{\n"
               "    public function ship(Invoice $i): void {}\n}\n")

    def test_a_new_cross_module_import(self):
        head = INVOICE.replace("use App\\Billing\\Line;\n", "use App\\Billing\\Line;\nuse App\\Shipping\\Carrier;\n"
                               "use Psr\\Log\\LoggerInterface;\n")
        self.start({"composer.json": COMPOSER, "src/Billing/Invoice.php": INVOICE, "src/Shipping/Carrier.php": self.CARRIER,
                    "tests/Billing/InvoiceTest.php": "<?php\nnamespace Tests\\Billing;\nuse App\\Shipping\\Carrier;\n"},
                   {"src/Billing/Invoice.php": head})
        out = self.output("import-graph-php")
        self.assertEqual((out["content"], out["heuristic"], out["stack"]), (True, True, "php"))
        self.assertEqual(out["modules"], "the namespace segment under a PSR-4 prefix of composer.json (`App\\`,"
                                         " `Tests\\`)")
        self.assertEqual(out["graph"]["base"], {
            "modules": {"src/Shipping/Carrier.php": "App\\Shipping", "src/Billing/Invoice.php": "App\\Billing"},
            "edges": [{"from": "src/Shipping/Carrier.php", "to": "src/Billing/Invoice.php", "line": 5}]},
            "a test file and a class outside the repository have no edge")
        self.assertEqual(self.kinds("import-graph-php"), [("src/Billing/Invoice.php", "import-edge-added", 6),
                                                          ("src/Billing/Invoice.php", "import-cycle-added", 6)])
        self.assertEqual([s["reason"] for s in out["signals"]], [
            "new import from module `App\\Billing` to module `App\\Shipping` (`src/Shipping/Carrier.php`)",
            "new cycle between modules `App\\Billing`, `App\\Shipping`"])
        self.assertEqual(out["new_cycles"][0]["modules"], ["App\\Billing", "App\\Shipping"])
        self.assertIsNone(out["layers"])
        self.assertNotIn("import-edge-added", read(os.path.join(self.root, "findings", "contracts.md")),
                         "the import graph feeds the structure step, not contracts")
        sheet = read(os.path.join(self.root, "findings", "structure.md"))
        self.assertIn("edge `App\\Billing` -> `App\\Shipping`", sheet)
        self.assertIn("cycle `App\\Billing`, `App\\Shipping`", sheet)
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `src/Billing/Invoice.php`: new import from module `App\\Billing` to module"
                      " `App\\Shipping`", glance)
        self.assertValid()

    def test_an_import_inside_the_module_or_already_there_is_no_signal(self):
        shop = "<?php\nnamespace App\\Shop;\nuse App\\Shipping\\Carrier;\nclass Cart {}\n"
        self.start({"src/Shop/Cart.php": shop, "src/Shop/Order.php": "<?php\nnamespace App\\Shop;\nclass Order {}\n",
                    "src/Shipping/Carrier.php": "<?php\nnamespace App\\Shipping;\nclass Carrier {}\n"},
                   {"src/Shop/Order.php": "<?php\nnamespace App\\Shop;\nuse App\\Shop\\Cart;\n"
                                          "use App\\Shipping\\{Carrier, Rate};\nclass Order {}\n"})
        out = self.output("import-graph-php")
        self.assertEqual(out["modules"], "the first two namespace segments (no PSR-4 prefix in composer.json)")
        self.assertEqual(self.kinds("import-graph-php"), [], "App\\Shop already depends on App\\Shipping")
        self.assertEqual(out["graph"]["head"]["edges"], [
            {"from": "src/Shop/Cart.php", "to": "src/Shipping/Carrier.php", "line": 3},
            {"from": "src/Shop/Order.php", "to": "src/Shipping/Carrier.php", "line": 4}])

    def test_no_php_to_graph_writes_no_graph(self):
        self.start({"app.py": "x = 1\n"}, {"app.py": "x = 2\n"})
        self.assertFalse(os.path.exists(os.path.join(self.root, "signals", "import-graph-php.json")))
        self.assertIn("not-evaluable (no stack adapter supplies an import graph)",
                      read(os.path.join(self.root, "findings", "structure.md")))

    def test_deptrac_layers_through_a_fake(self):
        config = ("deptrac:\n  paths: [./src]\n  layers:\n    - name: Domain\n    - name: Infra\n"
                  "  ruleset:\n    Domain: ~\n")
        fake = ('import json, os\nif "--version" in sys.argv:\n    print("deptrac 2.0.1")\n    sys.exit(0)\n'
                'args = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)\n'
                'assert sys.argv[1] == "analyse" and "--no-cache" in sys.argv, sys.argv\n'
                'tree = os.path.dirname(args["--config-file"])\n'
                'assert os.getcwd() == os.path.realpath(tree) and ".git" not in os.listdir(tree), tree\n'
                'files = {}\n'
                'for d, _, names in os.walk(os.path.join(tree, "src")):\n'
                '    for n in names:\n'
                '        p = os.path.join(d, n)\n'
                '        text = open(p).read()\n'
                '        if "namespace App\\\\Domain" in text and "use App\\\\Infra" in text:\n'
                '            files[p] = {"violations": 1, "messages": [{"message": "App\\\\Domain\\\\%s must not depend'
                ' on App\\\\Infra\\\\Db (Domain on Infra)" % n[:-4], "line": 3, "type": "error"}]}\n'
                'json.dump({"Report": {"Violations": len(files)}, "files": files}, open(args["--output"], "w"))\n'
                'sys.exit(1 if files else 0)\n')
        old = "<?php\nnamespace App\\Domain;\nuse App\\Infra\\Db;\nclass Old {}\n"
        self.start({"deptrac.yaml": config, "src/Domain/Old.php": old,
                    "src/Domain/User.php": "<?php\nnamespace App\\Domain;\nclass User {}\n",
                    "src/Infra/Db.php": "<?php\nnamespace App\\Infra;\nclass Db {}\n"},
                   {"src/Domain/User.php": "<?php\nnamespace App\\Domain;\nuse App\\Infra\\Db;\nclass User {}\n",
                    "src/Domain/Old.php": old + "\n"}, tools=[("deptrac", fake)])
        out = self.output("import-graph-php")
        self.assertEqual((out["tool"], out["gaps"]), ("deptrac@2.0.1", []))
        self.assertEqual(out["layers"], {"config": "deptrac.yaml", "checked": True, "violations": 2, "new": 1})
        self.assertIn(("src/Domain/User.php", "layer-violation", 3), self.kinds("import-graph-php"))
        self.assertNotIn("src/Domain/Old.php", [p for p, k, _ in self.kinds("import-graph-php") if k == "layer-violation"],
                         "a violation the base already has is not new")
        self.assertFalse(os.path.exists(os.path.join(self.root, ".tool-trees")), "the base tree is removed")
        self.assertValid()

    def test_a_php_deptrac_config_is_not_run(self):
        fake = 'print("deptrac 2.0.1")\nif "--version" not in sys.argv:\n    sys.exit(9)\n'
        self.start({"deptrac.php": "<?php\nreturn static function () {};\n",
                    "src/A/X.php": "<?php\nnamespace App\\A;\nclass X {}\n"},
                   {"src/A/X.php": "<?php\nnamespace App\\A;\nclass X { }\n"}, tools=[("deptrac", fake)])
        self.assertEqual(self.output("import-graph-php")["gaps"], [
            "deptrac not run: `deptrac.php` is PHP, and loading it runs the project's code; the layers of"
            " `deptrac.php` not checked"])


class TestParser(unittest.TestCase):
    def test_what_the_lexer_must_not_be_fooled_by(self):
        unit = php.parse(
            "<html><?php class Html {} ?></html>\n<?php\nnamespace App\\Core;\n\n"
            "use App\\Shipping\\{Carrier, Rate as R, function ship};\nuse const App\\X\\LIMIT;\n\n"
            "#[Attr(['a' => \"x]\", 'b' => 'class Fake {}'])]\nabstract class Kernel extends Base implements A, \\B\n{\n"
            "    // public function commented() {}\n    /* public function blocked() {} */\n"
            "    public function __construct(private R $rate, public readonly string $id = '') {}\n"
            "    abstract protected function boot(array &$x, int ...$rest): ?R;\n"
            "    public function run(): string\n    {\n        $f = function () use ($x) { return 1; };\n"
            "        $s = <<<EOT\n        class Fake { public function nope() {} }\n        EOT;\n"
            "        return new class { public function anon() {} } . Kernel::class . \"}\";\n    }\n}\n\n"
            "enum Suit: string\n{\n    case Hearts = 'H';\n    case Spades = 'S';\n    const Wild = self::Spades;\n}\n\n"
            "function helper($x = [1, 2]) {}\n")
        self.assertEqual(unit.imports, [("class", "App\\Shipping\\Carrier", 5), ("class", "App\\Shipping\\Rate", 5),
                                        ("function", "App\\Shipping\\ship", 5), ("const", "App\\X\\LIMIT", 6)])
        self.assertEqual(sorted(unit.classes), ["App\\Core\\Kernel", "App\\Core\\Suit", "Html"])
        kernel = unit.classes["App\\Core\\Kernel"]
        self.assertEqual((kernel["abstract"], kernel["extends"], kernel["implements"]),
                         (True, ["App\\Core\\Base"], ["App\\Core\\A", "B"]))
        self.assertEqual(sorted(kernel["methods"]), ["__construct", "boot", "run"])
        self.assertEqual(sorted(kernel["properties"]), ["id", "rate"])
        boot = kernel["methods"]["boot"]
        self.assertEqual((boot["visibility"], boot["abstract"], boot["returns"]), ("protected", True,
                                                                                  "?App\\Shipping\\Rate"))
        self.assertEqual([(p["name"], p["type"], p["byref"], p["variadic"]) for p in boot["params"]],
                         [("$x", "array", True, False), ("$rest", "int", False, True)])
        self.assertEqual((kernel["methods"]["run"]["line"], kernel["methods"]["run"]["end"]), (15, 22))
        self.assertEqual(sorted(unit.classes["App\\Core\\Suit"]["constants"]), ["Hearts", "Spades", "Wild"])
        self.assertEqual(sorted(unit.functions), ["app\\core\\helper"])

    def test_quick_imports_read_the_head_of_a_file(self):
        namespaces, imports = php.quick_imports(
            "<?php\nnamespace App\\Shop;\n\nuse App\\Billing\\{\n    Invoice,\n    Line\n};\nuse Other\\X;\n\n"
            "final class Cart\n{\n    use SomeTrait;\n}\nuse Not\\Read;\n")
        self.assertEqual(namespaces, ["App\\Shop"])
        self.assertEqual(imports, [("class", "App\\Billing\\Invoice", 4), ("class", "App\\Billing\\Line", 4),
                                   ("class", "Other\\X", 8)])

    def test_modules(self):
        m = php.Modules(COMPOSER, [])
        self.assertEqual((m.of("App\\Billing\\Invoice"), m.of("App\\Kernel"), m.of("Psr\\Log\\X"),
                          m.of_namespace("Tests\\Billing")), ("App\\Billing", "App", None, "Tests\\Billing"))
        m = php.Modules(None, ["Shop\\Cart"])
        self.assertEqual((m.of("Shop\\Cart\\Item"), m.of("Shop\\Kernel"), m.of("Vendor\\Lib\\X")),
                         ("Shop\\Cart", "Shop", None))


if __name__ == "__main__":
    unittest.main()
