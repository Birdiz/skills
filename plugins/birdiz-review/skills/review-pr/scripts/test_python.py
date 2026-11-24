"""Tests for the Python adapter, files in and files out:
python3 -I -m unittest discover -s <this directory>

Each repository test builds a tiny Python repository with a base on `main`
and a head on `feature/x`, runs run.py on it as the skill does, and reads
the detector outputs, the worksheets and the brief. griffe and
import-linter run as fake tools that print what the real ones print; the
griffe fake also takes griffe's own git steps (`git worktree add -b`, then
remove, prune, delete the branch) in the repository it runs in, which must
be the run's scratch repository, not the reviewed one. The parser tests
read Python text directly.
"""
import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import python  # noqa: E402
from test_detectors import DetectorCase  # noqa: E402
from test_run import GIT, read  # noqa: E402

INIT = ""
INVOICE = ('"""Invoices."""\nfrom dataclasses import dataclass\n\n\ndef total(lines, rate=1):\n'
           '    return len(lines) * rate\n\n\nclass Invoice:\n    def __init__(self, number):\n'
           '        self.number = number\n\n    def amount(self):\n        return 1\n\n'
           '    def _secret(self):\n        return 2\n')
CHECKOUT = ('from shop.billing.invoice import total, Invoice\n\n\ndef pay(number):\n'
            '    # total() in a comment is no reference\n    label = "total"\n'
            '    return total([]) + Invoice(number).amount()\n')
CARRIER = "from shop.billing import invoice\n\n\ndef ship(number):\n    return invoice.total([number])\n"
PYPROJECT = '[project]\nname = "shop"\nversion = "1.0"\n'


def git_out(repo, *args):
    return subprocess.run([GIT, "-C", repo] + list(args), stdout=subprocess.PIPE, universal_newlines=True,
                          check=True).stdout


def package(extra=None):
    files = {"pyproject.toml": PYPROJECT, "src/shop/__init__.py": INIT, "src/shop/billing/__init__.py": INIT,
             "src/shop/billing/invoice.py": INVOICE, "src/shop/checkout/__init__.py": INIT,
             "src/shop/checkout/pay.py": CHECKOUT}
    files.update(extra or {})
    return files


class TestPublicApi(DetectorCase):
    def test_a_renamed_public_function(self):
        self.start(package(), {"src/shop/billing/invoice.py": INVOICE.replace("def total(", "def grand_total(")})
        out = self.output("public-api")
        self.assertEqual((out["content"], out["heuristic"], out["tool"], out["languages"]),
                         (True, True, None, ["python"]))
        self.assertEqual(out["covered"], ["src/shop/billing/invoice.py"])
        self.assertEqual(self.kinds("public-api"), [("src/shop/billing/invoice.py", "function-removed", 5)])
        self.assertEqual(out["signals"][0]["reason"], "function `total()` removed; function `grand_total()` appears"
                                                      " in its place, a rename")
        self.assertIn("griffe not found on this machine: Python public API read by the heuristic signature diff",
                      out["gaps"])
        symbols = {s["symbol"]: s for s in self.output("fan-in")["symbols"]}
        self.assertEqual((symbols["total"]["change"], symbols["total"]["fan_in"]), ("removed", 2))
        self.assertEqual(symbols["total"]["refs"], ["src/shop/checkout/pay.py:1", "src/shop/checkout/pay.py:7"],
                         "a comment and a string are not references")
        self.assertEqual(self.kinds("fan-in"), [], "the public API diff signals the break, fan-in only counts")
        sheet = read(os.path.join(self.root, "findings", "contracts.md"))
        self.assertIn("| S1 `src/shop/billing/invoice.py:5` public-api `function-removed`: function `total()` removed;",
                      sheet)
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `src/shop/billing/invoice.py`: function `total()` removed", glance)
        self.assertIn("fan-in (heuristic): `total` in `src/shop/billing/invoice.py` 2 (removed)", self.brief())
        self.assertValid()

    def test_signatures_members_and_classes(self):
        base = ('import abc\nimport enum\nfrom dataclasses import dataclass\nfrom typing import Protocol, overload\n\n'
                '__all__ = ["fee", "Account", "Kind", "Line", "Payable", "parse", "LIMIT", "Base"]\n\n'
                'LIMIT: int = 10\n\n\ndef fee(amount, currency="EUR", *, rounding=2, **extra) -> int:\n    return 0\n\n\n'
                'def hidden(x):\n    return x\n\n\n'
                '@overload\ndef parse(x: int) -> int: ...\n@overload\ndef parse(x: str) -> str: ...\n'
                'def parse(x):\n    return x\n\n\n'
                'class Base:\n    pass\n\n\nclass Payable(Protocol):\n    def pay(self, amount: int) -> None: ...\n\n\n'
                'class Account(Base, abc.ABC):\n    kind: str = "card"\n\n    def __init__(self, owner: str):\n'
                '        self.owner = owner\n        self.balance: int = 0\n\n    @property\n    def label(self) -> str:\n'
                '        return self.owner\n\n    @label.setter\n    def label(self, value):\n        self.owner = value\n\n'
                '    def open(self, who, days=3):\n        return True\n\n    def close(self):\n        pass\n\n'
                '    def _debug(self):\n        pass\n\n\nclass Kind(enum.Enum):\n    CARD = enum.auto()\n'
                '    CASH = enum.auto()\n\n\n@dataclass\nclass Line:\n    sku: str\n    qty: int = 1\n')
        head = ('import abc\nimport enum\nfrom dataclasses import dataclass\nfrom typing import Protocol, overload\n\n'
                '__all__ = ["fee", "Account", "Kind", "Line", "Payable", "parse", "LIMIT", "Base", "hidden"]\n\n'
                'LIMIT: str = "10"\n\n\ndef fee(value: int, currency="USD", rounding=2) -> str:\n    return ""\n\n\n'
                'def hidden(x):\n    return x\n\n\n'
                '@overload\ndef parse(x: int) -> int: ...\n'
                'def parse(x):\n    return x\n\n\n'
                'class Base:\n    pass\n\n\nclass Payable(Protocol):\n    def pay(self, amount: int) -> None: ...\n\n'
                '    def refund(self) -> None: ...\n\n\n'
                'class Account(abc.ABC):\n    kind: int = 0\n\n    def __init__(self, owner: str, bank: str):\n'
                '        self.owner = owner\n\n    @property\n    def label(self) -> str:\n'
                '        return self.owner\n\n    def open(self, days, who=None):\n        return True\n\n'
                '    @abc.abstractmethod\n    def settle(self):\n        pass\n\n'
                '    def reopen(self):\n        pass\n\n'
                '    def _debug(self, verbose):\n        pass\n\n\nclass Kind(enum.Enum):\n    TRANSFER = enum.auto()\n'
                '    CARD = enum.auto()\n    CASH = enum.auto()\n\n\n@dataclass\nclass Line:\n    sku: str\n'
                '    price: float\n    qty: int = 1\n')
        self.start({"billing.py": base}, {"billing.py": head})
        reasons = {(s["kind"], s["reason"]) for s in self.output("public-api")["signals"]}
        self.assertEqual(reasons, {
            ("name-changed", "name `LIMIT`: type int -> str"),
            ("signature-changed", "function `fee()`: parameter `amount` renamed `value`: calls passing it by keyword"
                                  " break; default of `currency` 'EUR' -> 'USD'; "
                                  "`**extra` removed: calls passing extra keyword arguments break; return type int"
                                  " -> str"),
            ("signature-changed", "function `parse()`: overload `(x: str) -> str` removed or changed"),
            ("protocol-member-added", "protocol method `Payable.refund()` added: classes outside the diff that satisfy"
                                      " `Payable` must define it"),
            ("class-changed", "class `Account` no longer inherits `Base`: isinstance checks and inherited members"
                              " break"),
            ("property-changed", "attribute `Account.kind`: type str -> int"),
            ("signature-changed", "constructor `Account()`: new required parameter `bank`"),
            ("property-removed", "attribute `Account.balance` removed"),
            ("property-changed", "property `Account.label`: became read-only: writes outside the class break"),
            ("signature-changed", "method `Account.open()`: positional parameter `who` moved from position 1 to 2;"
                                  " positional parameter `days` moved from position 2 to 1; `days` became required:"
                                  " calls that omit it break"),
            ("method-removed", "method `Account.close()` removed"),
            ("abstract-method-added", "abstract method `Account.settle()` added: subclasses outside the diff must"
                                      " define it"),
            ("enum-member-changed", "member `Kind.CARD` value 1 -> 2: stored or sent values change meaning"),
            ("enum-member-changed", "member `Kind.CASH` value 2 -> 3: stored or sent values change meaning"),
            ("signature-changed", "constructor `Line()`: positional parameter `qty` moved from position 2 to 3;"
                                  " new required parameter `price`"),
        }, "names outside `__all__` and private members are not API; a type added where there was none is no"
           " change")

    def test_a_python_file_with_no_signal_is_skim(self):
        self.start(package(), {"src/shop/billing/invoice.py": INVOICE.replace("return 1\n", "return 1 + 0\n")})
        self.assertEqual(self.kinds("public-api") + self.kinds("import-graph-python"), [])
        self.assertEqual([(s["symbol"], s["change"]) for s in self.output("fan-in")["symbols"]],
                         [("Invoice.amount", "body")])
        skim = self.brief().split("## Skim")[1].split("## ")[0]
        self.assertIn("- `src/shop/billing/invoice.py`: covered by signals/import-graph-python.json,"
                      " signals/public-api.json, with no signal; no finding points at it; outside the risk map.", skim)
        self.assertValid()

    def test_unparsable_code_is_not_covered(self):
        self.start({"x.txt": "x\n"}, {"legacy.py": 'print "hello"\n', "ok.py": "def f():\n    return 1\n"})
        out = self.output("public-api")
        self.assertEqual([i["path"] for i in out["not_covered"]], ["legacy.py"])
        self.assertTrue(out["not_covered"][0]["reason"].startswith(
            "not readable as Python by %s at the head: Missing parentheses in call to 'print'" % python.INTERPRETER),
            out["not_covered"])
        self.assertEqual(out["covered"], ["ok.py"])
        unproven = self.brief().split("## Unproven")[1].split("## ")[0]
        self.assertIn("- `legacy.py`: signals/import-graph-python.json applies but did not cover it: not readable as"
                      " Python by %s at the head: Missing parentheses" % python.INTERPRETER, unproven)
        self.assertValid()

    def test_a_deleted_module_is_one_signal(self):
        self.start({"shop/__init__.py": "", "shop/old.py": "A = 1\n\n\ndef b():\n    pass\n\n\nclass C:\n    pass\n",
                    "shop/keep.py": "K = 1\n"}, {"shop/old.py": None})
        self.assertEqual([(s["kind"], s["reason"]) for s in self.output("public-api")["signals"]], [
            ("name-removed", "file deleted with 3 public symbols: `A`, `b`, `C`")])
        self.assertEqual(sorted(s["symbol"] for s in self.output("fan-in")["symbols"]), ["A", "C", "b"])

    def test_fan_in_counts_constructor_calls_and_members(self):
        head = INVOICE.replace("def __init__(self, number):", "def __init__(self, number, at):").replace(
            "def amount(self):", "def amount(self, rate):")
        self.start(package({"src/shop/checkout/cart.py": "from shop.billing import invoice\n\n\n"
                                                         "class Cart(invoice.Invoice):\n    pass\n\n\n"
                                                         "def show():\n    return f'{invoice.Invoice(1).amount()}'\n"
                                                         "\n\ndef other(factory):\n    return factory.Invoice(2)\n"}),
                   {"src/shop/billing/invoice.py": head})
        symbols = {s["symbol"]: s for s in self.output("fan-in")["symbols"]}
        self.assertEqual(sorted(symbols), ["Invoice.__init__", "Invoice.amount"])
        self.assertEqual(symbols["Invoice.__init__"]["refs"], ["src/shop/checkout/cart.py:4",
                                                               "src/shop/checkout/cart.py:9",
                                                               "src/shop/checkout/pay.py:7"],
                         "`factory.Invoice(` is another object's attribute")
        self.assertEqual(symbols["Invoice.amount"]["refs"], ["src/shop/checkout/cart.py:9",
                                                             "src/shop/checkout/pay.py:7"],
                         "the code in an f-string is searched")


GRIFFE = r'''
import os, subprocess, tempfile
if "--version" in sys.argv:
    print("griffe, version 2.4.1")
    sys.exit(0)
args = sys.argv[1:]
for flag in ("--no-inspection", "--no-color"):
    assert flag in args, args
assert args[0] == "check" and args[args.index("--format") + 1] == "github", args
pkg, search = args[1], args[args.index("--search") + 1]
def git(*a):
    done = subprocess.run(["git"] + list(a), capture_output=True, text=True)
    assert done.returncode == 0, (a, done.stdout + done.stderr)
    return done.stdout.strip()
repo = git("-C", pkg, "rev-parse", "--show-toplevel")  # as griffe finds the repository
assert ".tool-trees" in repo and repo.endswith("griffe-repo"), repo
seen = {}
for ref in (args[args.index("--against") + 1], args[args.index("--base-ref") + 1]):
    with tempfile.TemporaryDirectory(prefix="griffe-worktree-repo-%s-" % ref) as tmp:  # griffe's own steps
        where = os.path.join(tmp, ref)
        git("-C", repo, "worktree", "add", "-b", "griffe-" + ref, where, ref)
        with open(os.path.join(where, search, pkg, "billing", "invoice.py")) as fh:
            seen[ref] = fh.read()
        git("-C", repo, "worktree", "remove", where)
        git("-C", repo, "worktree", "prune")
        git("-C", repo, "branch", "-D", "griffe-" + ref)
if "def total(" in seen["review-base"] and "def total(" not in seen["review-head"]:
    path = os.path.join(search, pkg, "billing", "invoice.py")
    print("::warning file=%s,line=0,title=total::Public object was removed" % path, file=sys.stderr)
    print("::warning file=src/shop/__init__.py,line=1,title=total::Public object was removed", file=sys.stderr)
    sys.exit(1)
sys.exit(0)
'''


class TestGriffe(DetectorCase):
    def test_griffe_in_a_scratch_repository(self):
        self.start(package({"tools/run.py": "def main():\n    pass\n"}),
                   {"src/shop/billing/invoice.py": INVOICE.replace("def total(", "def grand_total("),
                    "tools/run.py": "def main(argv):\n    pass\n"}, tools=[("griffe", GRIFFE)])
        out = self.output("public-api")
        self.assertEqual((out["tool"], out["heuristic"]), ("griffe@2.4.1", True))
        self.assertEqual([(s["path"], s["kind"], s["reason"]) for s in out["signals"]], [
            ("src/shop/billing/invoice.py", "griffe:object-removed", "griffe: `total`: Public object was removed"),
            ("tools/run.py", "signature-changed", "function `main()`: new required parameter `argv`")],
            "griffe reads the package, the heuristic the file outside any package")
        self.assertEqual(out["gaps"], [
            "griffe not run on 1 file(s) outside a package present at both sides (`tools/run.py`): Python public API"
            " read by the heuristic signature diff",
            "griffe reported 1 breakage(s) in files the diff does not change (a re-export of a changed name): not"
            " signalled"])
        self.assertEqual(git_out(self.fx.repo, "for-each-ref", "--format=%(refname)").split(),
                         ["refs/heads/feature/x", "refs/heads/main"], "no branch written in the reviewed repository")
        self.assertEqual(len(git_out(self.fx.repo, "worktree", "list").splitlines()), 1)
        tools = {t["name"]: t for t in json.loads(read(os.path.join(self.root, "run.json")))["tools"]}
        self.assertEqual((tools["griffe"]["needs"], tools["griffe"]["installs"], tools["griffe"]["allowed"]),
                         ("nothing", False, True))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".tool-trees")), "the scratch repository is removed")
        self.assertValid()

    def test_a_failing_griffe_falls_back_to_the_heuristic(self):
        broken = ('if "--version" in sys.argv:\n    print("griffe 2.4.1")\n    sys.exit(0)\n'
                  'print("Traceback (most recent call last):\\n  File x\\nModuleNotFoundError: shop", file=sys.stderr)\n'
                  'sys.exit(1)\n')
        self.start(package(), {"src/shop/billing/invoice.py": INVOICE.replace("def total(", "def grand_total(")},
                   tools=[("griffe", broken)])
        out = self.output("public-api")
        self.assertEqual((out["tool"], out["heuristic"]), (None, True))
        self.assertEqual(out["gaps"], ["griffe failed on package `src/shop` (ModuleNotFoundError: shop): Python public"
                                       " API read by the heuristic signature diff"])
        self.assertEqual(self.kinds("public-api"), [("src/shop/billing/invoice.py", "function-removed", 5)])


class TestImports(DetectorCase):
    def test_a_new_cross_module_import(self):
        head = INVOICE.replace("from dataclasses import dataclass\n", "from dataclasses import dataclass\n"
                               "from ..shipping.carrier import ship\n")
        self.start(package({"src/shop/shipping/__init__.py": INIT, "src/shop/shipping/carrier.py": CARRIER,
                            "tests/test_invoice.py": "from shop.shipping.carrier import ship\n"}),
                   {"src/shop/billing/invoice.py": head})
        out = self.output("import-graph-python")
        self.assertEqual((out["content"], out["heuristic"], out["stack"], out["tool"], out["contracts"]),
                         (True, True, "python", None, None))
        self.assertTrue(out["modules"].startswith("a root's top-level package"), out["modules"])
        self.assertEqual(out["graph"]["base"], {
            "modules": {"src/shop/checkout/pay.py": "shop.checkout", "src/shop/billing/invoice.py": "shop.billing",
                        "src/shop/shipping/carrier.py": "shop.shipping"},
            "edges": [{"from": "src/shop/checkout/pay.py", "to": "src/shop/billing/invoice.py", "line": 1},
                      {"from": "src/shop/shipping/carrier.py", "to": "src/shop/billing/invoice.py", "line": 1}]},
            "a `from` import of a submodule maps to it; a test file has no edge")
        self.assertEqual(self.kinds("import-graph-python"), [
            ("src/shop/billing/invoice.py", "import-edge-added", 3),
            ("src/shop/billing/invoice.py", "import-cycle-added", 3)])
        self.assertEqual([s["reason"] for s in out["signals"]], [
            "new import from module `shop.billing` to module `shop.shipping` (`src/shop/shipping/carrier.py`)",
            "new cycle between modules `shop.billing`, `shop.shipping`"])
        self.assertNotIn("import-edge-added", read(os.path.join(self.root, "findings", "contracts.md")),
                         "the import graph feeds the structure step, not contracts")
        sheet = read(os.path.join(self.root, "findings", "structure.md"))
        self.assertIn("edge `shop.billing` -> `shop.shipping`", sheet)
        self.assertIn("cycle `shop.billing`, `shop.shipping`", sheet)
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `src/shop/billing/invoice.py`: new import from module `shop.billing` to module"
                      " `shop.shipping`", glance)
        self.assertValid()

    def test_apps_are_modules_and_imports_in_functions_count(self):
        self.start({"manage.py": "import os\n", "orders/__init__.py": "", "orders/models.py": "class Order:\n    pass\n",
                    "orders/views.py": "from . import models\n", "payments/__init__.py": "",
                    "payments/models.py": "class Payment:\n    pass\n"},
                   {"payments/models.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n"
                                          "    from orders.models import Order\n\n\nclass Payment:\n"
                                          "    def order(self):\n        from orders import views\n"
                                          "        return views\n"})
        out = self.output("import-graph-python")
        self.assertEqual(out["graph"]["head"]["edges"], [
            {"from": "payments/models.py", "to": "orders/models.py", "line": 3},
            {"from": "payments/models.py", "to": "orders/views.py", "line": 8}],
            "several top-level packages: each is a module, and `from . import models` stays inside `orders`")
        self.assertEqual(self.kinds("import-graph-python"), [("payments/models.py", "import-edge-added", 3)])


LINTER = r'''
import os
if "--version" in sys.argv:
    print("import-linter 2.17")
    sys.exit(0)
config = sys.argv[sys.argv.index("--config") + 1]
assert "--no-cache" in sys.argv, sys.argv
assert "PYTHONPATH" not in os.environ, os.environ["PYTHONPATH"]
assert sorted(os.listdir(".")) == sorted([config, "shop"]), os.listdir(".")  # only the config and the root package
links = []
for name in ("invoice", "legacy"):
    path = os.path.join("shop", "billing", name + ".py")
    if os.path.exists(path) and "shipping" in open(path).read():
        links.append("-   shop.billing.%s -> shop.shipping.carrier (l.3)" % name)
print("=============\nImport Linter\n=============\n\n---------\nContracts\n---------\n")
print("Analyzed 6 files, 3 dependencies.\n----------------------------------\n")
print("Billing is independent %s" % ("BROKEN" if links else "KEPT"))
print("Layers KEPT (2 ignored imports)\n")
print("Contracts: 1 kept, 1 broken." if links else "Contracts: 2 kept, 0 broken.")
if links:
    print("\n\n----------------\nBroken contracts\n----------------\n\nBilling is independent\n"
          "----------------------\n\nshop.billing is not allowed to import shop.shipping:\n\n" + "\n\n".join(links))
    sys.exit(1)
'''
LINTER_TOML = PYPROJECT + ('\n[tool.importlinter]\nroot_package = "shop"\n\n[[tool.importlinter.contracts]]\n'
                           'name = "Billing is independent"\ntype = "forbidden"\nsource_modules = ["shop.billing"]\n'
                           'forbidden_modules = ["shop.shipping"]\n')


class TestImportLinter(DetectorCase):
    def test_new_violations_through_a_fake(self):
        head = INVOICE.replace("from dataclasses import dataclass\n", "from dataclasses import dataclass\n"
                               "from shop.shipping.carrier import ship\n")
        self.start(package({"pyproject.toml": LINTER_TOML, "src/shop/shipping/__init__.py": INIT,
                            "src/shop/shipping/carrier.py": "def ship():\n    pass\n"}),
                   {"src/shop/billing/invoice.py": head}, tools=[("lint-imports", LINTER)])
        out = self.output("import-graph-python")
        self.assertEqual((out["tool"], out["gaps"]), ("import-linter@2.17", []))
        self.assertEqual(out["contracts"], {
            "config": "pyproject.toml", "checked": True, "kept": 1, "broken": 1, "new": 1, "broken_at_base": [],
            "results": {"Billing is independent": "broken", "Layers": "kept"}})
        self.assertEqual([(s["kind"], s["reason"], s.get("line")) for s in out["signals"]][-1], (
            "contract-broken", "new import-linter violation of `Billing is independent`: `shop.billing.invoice`"
                               " imports `shop.shipping.carrier`", 3))
        self.assertValid()

    def test_a_config_that_loads_code_is_not_run(self):
        toml = LINTER_TOML.replace('root_package = "shop"', 'root_package = "shop"\ncontract_types = ['
                                   '"mine: shop.contracts.Mine"]')
        self.start(package({"pyproject.toml": toml}), {"src/shop/billing/invoice.py": INVOICE + "\nX = 1\n"},
                   tools=[("lint-imports", 'assert False, "import-linter was run"\n')])
        out = self.output("import-graph-python")
        self.assertEqual(out["contracts"], {"config": "pyproject.toml", "checked": False})
        self.assertEqual(out["gaps"], ["import-linter not run: `pyproject.toml` registers its own contract types"
                                       " (`contract_types`), which imports the project's code; the contracts of"
                                       " `pyproject.toml` not checked"])
        self.start(package({"pyproject.toml": LINTER_TOML}), {"src/shop/billing/invoice.py": INVOICE + "\nX = 1\n"})
        self.assertEqual(self.output("import-graph-python")["gaps"], [
            "import-linter not found on this machine: the contracts of `pyproject.toml` not checked"])
        self.start(package({"pyproject.toml": LINTER_TOML.replace('"shop"', '"shop.billing"')}),
                   {"src/shop/billing/invoice.py": INVOICE + "\nX = 1\n"},
                   tools=[("lint-imports", 'assert False, "import-linter was run"\n')])
        self.assertEqual(self.output("import-graph-python")["gaps"], [
            "import-linter not run: root package `shop.billing` in `pyproject.toml` is dotted: finding it imports"
            " `shop`, the project's code; the contracts of `pyproject.toml` not checked"])

    def test_an_ini_config_and_a_contract_broken_at_the_base(self):
        ini = ("[importlinter]\nroot_package = shop\ndescription = 100% of billing stays apart\nexclude_type_checking_imports = True\n\n"
               "[importlinter:contract:1]\nname = Billing is independent\ntype = forbidden\nsource_modules = shop.billing\n"
               "forbidden_modules = shop.shipping\n")
        legacy = "\n\nfrom shop.shipping import carrier\n"
        head = INVOICE.replace("from dataclasses import dataclass\n", "from dataclasses import dataclass\n"
                               "from shop.shipping.carrier import ship\n")
        self.start(package({".importlinter": ini, "src/shop/shipping/__init__.py": INIT,
                            "src/shop/shipping/carrier.py": "def ship():\n    pass\n",
                            "src/shop/billing/legacy.py": legacy}),
                   {"src/shop/billing/invoice.py": head, "src/shop/billing/legacy.py": legacy + "X = 1\n"},
                   tools=[("lint-imports", LINTER)])
        out = self.output("import-graph-python")
        self.assertEqual((out["tool"], out["gaps"], out["contracts"]["config"], out["contracts"]["broken_at_base"]),
                         ("import-linter@2.17", [], ".importlinter", ["Billing is independent"]))
        self.assertEqual([(s["path"], s["kind"]) for s in out["signals"] if s["kind"] == "contract-broken"],
                         [("src/shop/billing/invoice.py", "contract-broken")],
                         "the import the base already broke the contract with is not new")


class TestNoPython(DetectorCase):
    def test_no_python_file_in_the_diff_writes_no_graph(self):
        self.start({"app.py": "x = 1\n", "README.md": "a\n"}, {"README.md": "b\n"})
        self.assertFalse(os.path.exists(os.path.join(self.root, "signals", "import-graph-python.json")))


class TestParser(unittest.TestCase):
    def test_what_is_public(self):
        unit = python.parse("import os\nfrom .models import Order\nfrom typing import Any as Any\n_x = 1\nY = 2\n"
                            "def f(): pass\ndef _g(): pass\n", "shop/__init__.py")
        self.assertEqual(sorted(k for k in unit.api if unit.public(k)), ["Any", "Order", "Y", "f"],
                         "an `__init__.py` re-exports its relative imports and its `X as X` aliases")
        unit = python.parse("from .models import Order\n__all__ = ['f']\n__all__ += ['Order']\ndef f(): pass\n"
                            "def g(): pass\n", "shop/api.py")
        self.assertEqual(sorted(k for k in unit.api if unit.public(k)), ["Order", "f"])
        base = python.parse("from .impl import *\n__all__ = ['foo', 'bar']\n", "shop/api.py")
        head = python.parse("from .impl import *\n__all__ = ['foo']\n", "shop/api.py")
        self.assertEqual([(c["kind"], c["reason"], c["line"]) for c in python.api_changes(base, head)],
                         [("name-removed", "name `bar` no longer in `__all__`", 2)])
        unit = python.parse("def f(): pass\n", "shop/_impl/core.py")
        self.assertFalse(unit.public("f"), "a module under a private part exports only its `__all__`")
        with self.assertRaises(python.ParseError):
            python.parse("def f(:\n", "x.py")
        with self.assertRaises(python.ParseError, msg="too deep for ast.unparse: not covered, the run goes on"):
            python.parse("import enum\nclass F(enum.Flag):\n    A = 1\n    ALL = %s\n" % " | ".join(["A"] * 2000),
                         "x.py")

    def test_signature_rules(self):
        def diff(a, b):
            return python.sig_diff(python.parse("def f%s: pass\n" % a, "m.py").api["f"]["sigs"][0],
                                   python.parse("def f%s: pass\n" % b, "m.py").api["f"]["sigs"][0])
        self.assertEqual(diff("(a, /, b)", "(x, /, b)"), [], "a positional-only parameter renamed is no change")
        self.assertEqual(diff("(a, b=1)", "(a, b=1, c=2)"), [])
        self.assertEqual(diff("(a)", "(a: int)"), [], "a type added where there was none is no change")
        self.assertEqual(diff("(a, b)", "(a, *, b)"), ["`b` became keyword-only: calls passing it by position break"])
        self.assertEqual(diff("(a, *, b)", "(a, **kw)"), [], "`**kw` takes what was passed as `b`")
        self.assertEqual(diff("(a)", "(b, **kw)"), ["parameter `a` renamed `b`: calls passing it by keyword break"],
                         "`f(a=1)` lands in `**kw` and leaves `b` missing")
        self.assertEqual(diff("(a)", "(b=None, **kw)"), [])
        self.assertEqual(diff("(a=1)", "(a)"), ["`a` became required: calls that omit it break"])
        self.assertEqual(diff("(a, *args)", "(a)"), ["`*args` removed: calls passing extra positional arguments"
                                                      " break"])
        self.assertEqual(diff("(a) -> int", "(a) -> str"), ["return type int -> str"])
        unit = python.parse("async def g(): pass\n", "m.py")
        self.assertEqual(python.sig_diff(python.parse("def g(): pass\n", "m.py").api["g"]["sigs"][0],
                                         unit.api["g"]["sigs"][0]), ["became async: callers must await it"])

    def test_classes(self):
        unit = python.parse("import enum\nfrom dataclasses import dataclass, field, KW_ONLY\n"
                            "class F(enum.IntFlag):\n    A = enum.auto()\n    B = enum.auto()\n    C = 8\n"
                            "    D = enum.auto()\n"
                            "@dataclass\nclass D:\n    a: int\n    b: list = field(default_factory=list)\n"
                            "    c: int = field(init=False)\n    _: KW_ONLY\n    d: str = 'x'\n", "m.py")
        self.assertEqual({k: m["value"] for k, m in unit.api["F"]["members"].items()},
                         {"A": "1", "B": "2", "C": "8", "D": "16"})
        enums = python.parse("import enum\nclass E(enum.Enum):\n    A = 5\n    B = 1\n    C = enum.auto()\n"
                            "    note: str\nclass G(enum.Flag):\n    A = 3\n    B = enum.auto()\n    C = 1 << 3\n"
                            "    D = enum.auto()\n", "m.py")
        self.assertEqual({k: (m["kind"], m.get("value")) for k, m in enums.api["E"]["members"].items()},
                         {"A": ("member", "5"), "B": ("member", "1"), "C": ("member", "6"), "note": ("attribute", None)})
        self.assertEqual({k: m["value"] for k, m in enums.api["G"]["members"].items()},
                         {"A": "3", "B": "4", "C": "1 << 3", "D": "16"})
        sig = unit.api["D"]["members"]["__init__"]["sigs"][0]
        self.assertEqual([(p["name"], p["kind"], p["default"]) for p in sig["params"]],
                         [("a", "pos", None), ("b", "pos", "list()"), ("d", "kwonly", "'x'")])

    def test_strip_blanks_strings_and_comments(self):
        text = 'x = "total"  # total\ny = f"{total(1)} total"\nz = """\ntotal\n"""\n'
        out = python.strip(text)
        self.assertEqual(out.count("\n"), text.count("\n"))
        self.assertEqual(out.count("total"), 1, "the code inside an f-string is kept, its text blanked")
        self.assertEqual(python.strip('s = f"{{total}} {x}"\n').count("total"), 0, "`{{` is text")
        self.assertEqual(python.strip("x = (\n"), "x = (\n", "a text that can't be tokenized stays as it is")

    def test_project_resolution_and_modules(self):
        files = ["pyproject.toml", "src/shop/__init__.py", "src/shop/core.py", "src/shop/billing/__init__.py",
                 "src/shop/billing/invoice.py", "scripts/tool.py", "scripts/helper.py", "tests/__init__.py",
                 "services/api/pyproject.toml", "services/api/app/__init__.py", "services/api/app/main.py"]
        p = python.Project(files)
        self.assertEqual(p.names["src/shop/billing/invoice.py"], "shop.billing.invoice")
        self.assertEqual(p.module_of("src/shop/billing/invoice.py"), "shop.billing")
        self.assertEqual(p.module_of("src/shop/core.py"), "shop")
        self.assertEqual(p.module_of("services/api/app/main.py"), "services/api:app")
        self.assertEqual(p.module_of("scripts/tool.py"), "scripts", "outside a package, a module is a directory")
        self.assertEqual(p.resolve("src/shop/billing/invoice.py", 2, "core", []), ["src/shop/core.py"])
        self.assertEqual(p.resolve("src/shop/core.py", 0, "shop.billing", ["invoice", "Thing"]),
                         ["src/shop/billing/invoice.py", "src/shop/billing/__init__.py"])
        self.assertEqual(p.resolve("src/shop/core.py", 0, "shop.billing.invoice.Thing", []),
                         ["src/shop/billing/invoice.py"])
        self.assertEqual(p.resolve("scripts/tool.py", 0, "helper", []), ["scripts/helper.py"],
                         "a script imports the modules beside it")
        self.assertEqual(p.resolve("src/shop/core.py", 0, "os", []), [])
        self.assertEqual(p.resolve("src/shop/core.py", 3, "", ["x"]), [], "beyond the top-level package")
        ns = python.Project(["pyproject.toml", "src/acme/billing/__init__.py", "src/acme/billing/invoice.py",
                             "src/acme/shipping/__init__.py", "src/acme/shipping/carrier.py"])
        self.assertEqual(ns.resolve("src/acme/billing/invoice.py", 0, "acme.shipping.carrier", []),
                         ["src/acme/shipping/carrier.py"], "`acme` is a namespace package under `src/`")
        self.assertEqual(ns.module_of("src/acme/billing/invoice.py"), "acme.billing")
        stray = python.Project(["services/a/pyproject.toml", "services/a/app/__init__.py", "services/a/app/main.py",
                                "services/b/pyproject.toml", "services/b/logging.py", "services/b/requests/x.py"])
        self.assertEqual(stray.resolve("services/a/app/main.py", 0, "logging", []), [],
                         "another root's loose module is not the standard library's `logging`")
        twins = python.Project(["core/kit/__init__.py", "plugins/a/core/kit/__init__.py", "plugins/a/scripts/run.py"])
        self.assertEqual(twins.resolve("plugins/a/scripts/run.py", 0, "kit", []), ["plugins/a/core/kit/__init__.py"],
                         "of two copies of a package, the one nearest the importer")
        self.assertEqual(p.resolve("src/shop/core.py", 0, "shop.billing.invoice", [],
                                   exists=lambda f: f != "src/shop/billing/invoice.py"), ["src/shop/billing/__init__.py"])

    def test_tool_output(self):
        text = ("::warning file=src/shop/a.py,line=12,title=f(x)::Parameter was removed\n"
                "WARNING    something else\n"
                "::warning file=src/shop/a.py,line=0,title=g::Public object was removed\n"
                "::warning file=src/shop/a.py,line=3,title=C.x::Attribute types are incompatible: int -> str\n")
        self.assertEqual([(b["line"], b["title"], b["slug"], b["change"]) for b in python.griffe_breakages(text)], [
            (12, "f(x)", "parameter-removed", ""), (None, "g", "object-removed", ""),
            (3, "C.x", "attribute-type-changed", "int -> str")])
        self.assertIsNone(python.linter_report("Could not read any configuration.\n"))
        report = python.linter_report("A KEPT\nB layers BROKEN\n\nContracts: 1 kept, 1 broken.\n\n\n"
                                      "----------------\nBroken contracts\n----------------\n\nB layers\n--------\n\n"
                                      "- a.low -> a.high (l.4, l.9)\n  a.high -> a.top (l.?)\n")
        self.assertEqual(report["results"], {"A": "kept", "B layers": "broken"})
        self.assertEqual(report["links"], [("B layers", "a.low", "a.high", 4), ("B layers", "a.high", "a.top", None)])


if __name__ == "__main__":
    unittest.main()
