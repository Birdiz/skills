"""Tests for the TypeScript adapter, files in and files out:
python3 -I -m unittest discover -s <this directory>

Each repository test builds a tiny TypeScript repository with a base on
`main` and a head on `feature/x`, runs run.py on it as the skill does, and
reads the detector outputs, the worksheets and the brief. dependency-cruiser
and graphql-inspector run as fake tools that print what the real ones
print; API Extractor as a fake that fails the test if it is ever run. The
parser tests read TypeScript text directly, for what the lexer must not be
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
import typescript  # noqa: E402
from test_detectors import DetectorCase  # noqa: E402
from test_run import read  # noqa: E402

PACKAGE = json.dumps({"name": "shop", "dependencies": {"zod": "^3.0.0"}})
INVOICE = ("import { z } from 'zod';\n\nexport interface Line {\n  sku: string;\n  qty: number;\n}\n\n"
           "export function total(lines: Line[]): number {\n  return lines.length;\n}\n\n"
           "export class Invoice {\n  constructor(public id: string) {}\n\n  amount(): number {\n    return 1;\n  }\n\n"
           "  private secret(): number {\n    return 2;\n  }\n}\n")
CHECKOUT = ("import { total, Invoice } from '../billing/invoice';\n\n"
            "export function pay(id: string): number {\n  // total() in a comment is no reference\n"
            "  const label = 'total';\n  return total([]) + new Invoice(id).amount();\n}\n")


class TestPublicApi(DetectorCase):
    def test_a_renamed_export(self):
        self.start({"package.json": PACKAGE, "src/billing/invoice.ts": INVOICE, "src/shop/checkout.ts": CHECKOUT},
                   {"src/billing/invoice.ts": INVOICE.replace("function total(", "function grandTotal(")})
        out = self.output("public-api")
        self.assertEqual((out["content"], out["heuristic"], out["tool"], out["languages"]),
                         (True, True, None, ["typescript"]))
        self.assertEqual(out["covered"], ["src/billing/invoice.ts"])
        self.assertEqual(self.kinds("public-api"), [("src/billing/invoice.ts", "export-removed", 8)])
        self.assertEqual(out["signals"][0]["reason"], "export `total` (a function) removed; `grandTotal` appears in"
                                                      " its place, a rename")
        self.assertTrue(any(g.startswith("api-extractor not run (not found on this machine): it needs a build")
                            for g in out["gaps"]), out["gaps"])
        symbols = {s["symbol"]: s for s in self.output("fan-in")["symbols"]}
        self.assertEqual((symbols["total"]["change"], symbols["total"]["fan_in"]), ("removed", 2))
        self.assertEqual(symbols["total"]["refs"], ["src/shop/checkout.ts:1", "src/shop/checkout.ts:6"],
                         "a comment and a string are not references")
        self.assertEqual(self.kinds("fan-in"), [], "the public API diff signals the break, fan-in only counts")
        sheet = read(os.path.join(self.root, "findings", "contracts.md"))
        self.assertIn("| S1 `src/billing/invoice.ts:8` public-api `export-removed`: export `total` (a function)"
                      " removed;", sheet)
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `src/billing/invoice.ts`: export `total` (a function) removed", glance)
        self.assertIn("fan-in (heuristic): `total` in `src/billing/invoice.ts` 2 (removed)", self.brief())
        self.assertValid()

    def test_signatures_members_interfaces_types_and_enums(self):
        base = ("export interface Payable {\n  pay(amount: number): void;\n  note?: string;\n}\n\n"
                "export type Status = 'open' | 'paid';\n\nexport enum Kind { Card, Cash }\n\n"
                "export class Account implements Payable {\n  static LIMIT = 10;\n  protected owner: string = '';\n"
                "  pay(amount: number): void {}\n  open(who: string, days = 3): boolean { return true; }\n"
                "  close(): void {}\n  /** @internal */\n  debug(): void {}\n}\n\n"
                "export const fee = (amount: number): number => amount;\n")
        head = ("export interface Payable {\n  pay(amount: number): void;\n  note: string;\n  refund(): void;\n}\n\n"
                "export type Status = 'open' | 'paid' | 'void';\n\nexport enum Kind { Transfer, Card, Cash }\n\n"
                "export abstract class Account implements Payable {\n  static LIMIT = 10;\n  protected owner = 0;\n"
                "  note = '';\n  pay(amount: number): void {}\n  refund(): void {}\n"
                "  open(name: string, days: number, now: boolean): boolean { return true; }\n"
                "  private close(): void {}\n}\n\n"
                "export function fee(amount: number, currency: string): number { return amount; }\n")
        self.start({"src/billing/account.ts": base}, {"src/billing/account.ts": head})
        reasons = {(s["kind"], s["reason"]) for s in self.output("public-api")["signals"]}
        self.assertEqual(reasons, {
            ("member-changed", "member `Payable.note`: became required: objects outside the diff must provide it"),
            ("interface-member-added", "required member `Payable.refund` added: implementations and object literals"
                                       " outside the diff must provide it"),
            ("type-changed", "type `Status`: 'open'|'paid' -> 'open'|'paid'|'void'"),
            ("enum-member-changed", "member `Kind.Card` value 0 -> 1: stored or sent values change meaning"),
            ("enum-member-changed", "member `Kind.Cash` value 1 -> 2: stored or sent values change meaning"),
            ("class-changed", "class `Account` became abstract: `new Account()` breaks"),
            ("property-changed", "protected property `Account.owner`: type string -> none"),
            ("signature-changed", "public method `Account.open()`: type of `days` none -> number; `days` became"
                                  " required: calls that omit it break; new required parameter `now`"),
            ("visibility-reduced", "method `Account.close` public -> private"),
            ("signature-changed", "function `fee()`: new required parameter `currency`"),
        }, "a renamed parameter is no break in TypeScript, an @internal method is not API, and types are compared"
           " as written")

    def test_fan_in_counts_constructor_calls_and_members(self):
        head = INVOICE.replace("constructor(public id: string)", "constructor(public id: string, at: Date)").replace(
            "amount(): number", "amount(rate: number): number")
        self.start({"src/billing/invoice.ts": INVOICE, "src/shop/checkout.ts": CHECKOUT,
                    "src/shop/cart.tsx": "import { Invoice } from '../billing/invoice';\n"
                                         "export const Cart = () => <p>{new Invoice('x').amount()}</p>;\n"},
                   {"src/billing/invoice.ts": head})
        symbols = {s["symbol"]: s for s in self.output("fan-in")["symbols"]}
        self.assertEqual(sorted(symbols), ["Invoice.amount", "Invoice.constructor"])
        self.assertEqual((symbols["Invoice.constructor"]["change"], symbols["Invoice.constructor"]["fan_in"]),
                         ("signature", 2))
        self.assertEqual(symbols["Invoice.amount"]["refs"], ["src/shop/cart.tsx:2", "src/shop/checkout.ts:6"],
                         "JSX is code: its expressions are searched")

    def test_a_typescript_file_with_no_signal_is_skim(self):
        self.start({"package.json": PACKAGE, "src/billing/invoice.ts": INVOICE},
                   {"src/billing/invoice.ts": INVOICE.replace("return lines.length;", "return lines.length + 0;")})
        self.assertEqual(self.kinds("public-api") + self.kinds("import-graph-typescript"), [])
        self.assertEqual(self.output("fan-in")["symbols"][0]["change"], "body")
        skim = self.brief().split("## Skim")[1].split("## ")[0]
        self.assertIn("- `src/billing/invoice.ts`: covered by signals/import-graph-typescript.json,"
                      " signals/public-api.json, with no signal; no finding points at it; outside the risk map.", skim)
        self.assertValid()

    def test_unreadable_code_and_commonjs_are_not_covered(self):
        self.start({"x.txt": "x\n"}, {"src/broken.ts": "export function f() {\n  return `never closed;\n}\n",
                                      "src/legacy.js": "const x = require('./x');\nmodule.exports = { x };\n",
                                      "public/bundle.mjs": "export const a=1;" + "var b=2;" * 1000 + "\n",
                                      "src/page.vue": "<template><p>x</p></template>\n"})
        out = self.output("public-api")
        self.assertNotIn("src/page.vue", out["applies_to"])
        self.assertEqual(sorted((i["path"], i["reason"]) for i in out["not_covered"]), [
            ("public/bundle.mjs", "minified or bundled at the head (a line of 8017 characters): not read as source"),
            ("src/broken.ts", "not readable as TypeScript at the head: a template literal never closes (line 2)"),
            ("src/legacy.js", "exports through CommonJS (`module.exports`) at the head, which this version does not"
                              " read")])
        graph = self.output("import-graph-typescript")
        self.assertEqual(graph["covered"], ["src/legacy.js"], "its imports are read all the same")
        unproven = self.brief().split("## Unproven")[1].split("## ")[0]
        self.assertIn("- `src/page.vue`: no content detector reads this file type", unproven)
        self.assertIn("- `src/legacy.js`: signals/public-api.json applies but did not cover it", unproven)
        self.assertValid()

    def test_a_deleted_module_is_one_signal(self):
        self.start({"src/old.ts": "export const a = 1;\nexport function b() {}\nexport class C {}\n",
                    "src/keep.ts": "export const k = 1;\n"}, {"src/old.ts": None})
        self.assertEqual([(s["kind"], s["reason"]) for s in self.output("public-api")["signals"]], [
            ("export-removed", "file deleted with 3 public symbols: `a`, `b`, `C`")])
        self.assertEqual(sorted(s["symbol"] for s in self.output("fan-in")["symbols"]), ["C", "a", "b"],
                         "fan-in still counts each")

    def test_api_extractor_is_never_run(self):
        scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, scratch)
        marker = os.path.join(scratch, "api-extractor-ran")
        fake = ('if sys.argv[1:] == ["--version"]:\n    print("api-extractor 7.47.0")\n    sys.exit(0)\n'
                'open(%r, "w").write(" ".join(sys.argv))\nsys.exit(3)\n' % marker)
        self.start({"src/a.ts": "export function run(): void {}\n"}, {"src/a.ts": "export function go(): void {}\n"},
                   tools=[("api-extractor", fake)])
        self.assertFalse(os.path.exists(marker), "API Extractor was run")
        tools = {t["name"]: t for t in json.loads(read(os.path.join(self.root, "run.json")))["tools"]}
        self.assertEqual((tools["api-extractor"]["found"], tools["api-extractor"]["needs"],
                          tools["api-extractor"]["allowed"]), (True, "build", False))
        self.assertEqual((tools["dependency-cruiser"]["needs"], tools["dependency-cruiser"]["installs"],
                          tools["dependency-cruiser"]["allowed"]), ("dependencies", False, True))
        self.assertTrue(any(g.startswith("api-extractor not run (found on this machine)")
                            for g in self.output("public-api")["gaps"]))


SHIPPING = "import { Invoice } from '@/billing/invoice';\n\nexport function ship(i: Invoice): void {}\n"
TSCONFIG = ('{\n  // comments and trailing commas are allowed\n  "compilerOptions": {\n    "baseUrl": ".",\n'
            '    "paths": { "@/*": ["src/*"], },\n  },\n}\n')


class TestImports(DetectorCase):
    def test_a_new_cross_module_import(self):
        head = INVOICE.replace("import { z } from 'zod';\n", "import { z } from 'zod';\n"
                               "import { ship } from '../shipping/carrier';\n")
        self.start({"package.json": PACKAGE, "tsconfig.json": TSCONFIG, "src/billing/invoice.ts": INVOICE,
                    "src/shipping/carrier.ts": SHIPPING,
                    "src/billing/invoice.test.ts": "import { ship } from '../shipping/carrier';\n"},
                   {"src/billing/invoice.ts": head})
        out = self.output("import-graph-typescript")
        self.assertEqual((out["content"], out["heuristic"], out["stack"], out["tool"]), (True, True, "typescript", None))
        self.assertTrue(out["modules"].startswith("the first directory under a source root"), out["modules"])
        self.assertIn("path aliases `@/*`", out["modules"])
        self.assertEqual(out["graph"]["base"], {
            "modules": {"src/shipping/carrier.ts": "src/shipping", "src/billing/invoice.ts": "src/billing"},
            "edges": [{"from": "src/shipping/carrier.ts", "to": "src/billing/invoice.ts", "line": 1}]},
            "a tsconfig alias resolves; a test file and a package have no edge")
        self.assertEqual(self.kinds("import-graph-typescript"), [
            ("src/billing/invoice.ts", "import-edge-added", 2), ("src/billing/invoice.ts", "import-cycle-added", 2)])
        self.assertEqual([s["reason"] for s in out["signals"]], [
            "new import from module `src/billing` to module `src/shipping` (`src/shipping/carrier.ts`)",
            "new cycle between modules `src/billing`, `src/shipping`"])
        self.assertIn("dependency-cruiser not found on this machine: imports resolved by the parser (relative paths,"
                      " tsconfig paths, workspace packages)", out["gaps"])
        self.assertNotIn("import-edge-added", read(os.path.join(self.root, "findings", "contracts.md")),
                         "the import graph feeds the structure step, not contracts")
        sheet = read(os.path.join(self.root, "findings", "structure.md"))
        self.assertIn("edge `src/billing` -> `src/shipping`", sheet)
        self.assertIn("cycle `src/billing`, `src/shipping`", sheet)
        glance = self.brief().split("## Glance")[1].split("## ")[0]
        self.assertIn("- `src/billing/invoice.ts`: new import from module `src/billing` to module `src/shipping`",
                      glance)
        self.assertValid()

    def test_workspace_packages_and_reexports(self):
        pkg = lambda name: json.dumps({"name": name, "main": "dist/index.js"})
        self.start({"package.json": json.dumps({"private": True, "workspaces": ["packages/*"]}),
                    "packages/billing/package.json": pkg("@acme/billing"),
                    "packages/billing/src/index.ts": "export * from './invoice';\n",
                    "packages/billing/src/invoice.ts": "export const total = 1;\n",
                    "packages/web/package.json": pkg("@acme/web"),
                    "packages/web/src/pages/home.tsx": "export const Home = () => <main>home</main>;\n"},
                   {"packages/web/src/pages/home.tsx": "import { total } from '@acme/billing';\n"
                                                       "export const Home = () => <main>{total}</main>;\n"})
        out = self.output("import-graph-typescript")
        self.assertEqual(out["graph"]["head"]["edges"], [
            {"from": "packages/web/src/pages/home.tsx", "to": "packages/billing/src/index.ts", "line": 1}],
            "a package's `main` in `dist/` maps to its `src/`; the barrel's re-export stays in its module")
        self.assertEqual(out["graph"]["head"]["modules"], {"packages/web/src/pages/home.tsx": "packages/web/src/pages",
                                                           "packages/billing/src/index.ts": "packages/billing/src"})
        self.assertIn("workspace packages `@acme/billing`, `@acme/web`", out["modules"])
        self.assertEqual([k for _, k, _ in self.kinds("import-graph-typescript")], ["import-edge-added"])

    def test_dependency_cruiser_through_a_fake(self):
        fake = ('import json, os, re\nif "--version" in sys.argv:\n    print("18.9.0")\n    sys.exit(0)\n'
                'for flag in ("--no-config", "--ts-pre-compilation-deps"):\n'
                '    assert flag in sys.argv, sys.argv\n'
                'assert ".git" not in os.listdir("."), os.getcwd()\n'
                'out = sys.argv[sys.argv.index("--output-to") + 1]\n'
                'modules = []\n'
                'for d, dirs, names in os.walk("."):\n'
                '    dirs[:] = [x for x in dirs if x != "node_modules"]\n'
                '    for n in names:\n'
                '        if not n.endswith(".ts"):\n'
                '            continue\n'
                '        src = os.path.relpath(os.path.join(d, n))\n'
                '        deps = []\n'
                '        for spec in re.findall(r"from \'([^\']+)\'", open(src).read()):\n'
                '            if spec.startswith("~billing/"):\n'
                '                deps.append({"resolved": "src/billing/" + spec[9:] + ".ts", "module": spec})\n'
                '            elif spec.startswith("."):\n'
                '                r = os.path.normpath(os.path.join(os.path.dirname(src), spec)) + ".ts"\n'
                '                deps.append({"resolved": r, "module": spec})\n'
                '            else:\n'
                '                deps.append({"resolved": spec, "module": spec, "couldNotResolve": True})\n'
                '        modules.append({"source": src, "dependencies": deps})\n'
                'json.dump({"modules": modules, "summary": {"violations": []}}, open(out, "w"))\n')
        self.start({"src/billing/invoice.ts": INVOICE, "src/shipping/carrier.ts": "export const x = 1;\n"},
                   {"src/shipping/carrier.ts": "import { total } from '~billing/invoice';\nexport const x = total;\n"},
                   tools=[("depcruise", fake)])
        out = self.output("import-graph-typescript")
        self.assertEqual((out["tool"], out["gaps"]), ("dependency-cruiser@18.9.0", []))
        self.assertEqual(out["graph"]["head"]["edges"], [
            {"from": "src/shipping/carrier.ts", "to": "src/billing/invoice.ts", "line": None}],
            "the alias only dependency-cruiser resolves makes the edge")
        self.assertEqual(self.kinds("import-graph-typescript"), [("src/shipping/carrier.ts", "import-edge-added", None)])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".tool-trees")), "the base tree is removed")
        self.assertValid()

    def test_dependency_cruiser_that_skips_typescript_is_not_used(self):
        fake = ('import json\nif "--version" in sys.argv:\n    print("18.9.0")\n    sys.exit(0)\n'
                'json.dump({"modules": []}, open(sys.argv[sys.argv.index("--output-to") + 1], "w"))\n')
        self.start({"src/billing/invoice.ts": INVOICE, "src/shipping/carrier.ts": "export const x = 1;\n"},
                   {"src/shipping/carrier.ts": "import { total } from '../billing/invoice';\nexport const x = total;\n"},
                   tools=[("depcruise", fake)])
        out = self.output("import-graph-typescript")
        self.assertIsNone(out["tool"])
        self.assertEqual(out["gaps"], ["dependency-cruiser not used: it did not read `src/shipping/carrier.ts` at the"
                                       " head (no TypeScript compiler installed beside it?); imports resolved by the"
                                       " parser"])
        self.assertEqual(self.kinds("import-graph-typescript"), [("src/shipping/carrier.ts", "import-edge-added", 1)])


SCHEMA = "type User {\n  id: ID!\n  name: String\n}\n\ntype Query {\n  me: User\n}\n"


class TestNoTypescript(DetectorCase):
    def test_a_package_json_beside_python_writes_no_graph(self):
        self.start({"package.json": PACKAGE, "app.py": "x = 1\n"}, {"app.py": "x = 2\n"})
        self.assertFalse(os.path.exists(os.path.join(self.root, "signals", "import-graph-typescript.json")))
        self.assertIn("not-evaluable (no stack adapter supplies an import graph)",
                      read(os.path.join(self.root, "findings", "structure.md")))


class TestGraphql(DetectorCase):
    FAKE = ('if "--version" in sys.argv:\n    print("7.0.10")\n    sys.exit(0)\n'
            'old, new = open(sys.argv[2]).read(), open(sys.argv[3]).read()\n'
            'if "name: String" in old and "name: String" not in new:\n'
            '    print("[log] \\nDetected the following changes (2) between schemas:\\n")\n'
            '    print("[log] \\u2716  Field name was removed from object type User")\n'
            '    print("[log] \\u26a0  Default value changed on argument limit")\n'
            '    print("[log] \\u2714  Type Account was added")\n'
            '    print("[error] Detected 1 breaking change")\n'
            '    sys.exit(1)\n'
            'print("[success] No changes detected")\n')

    def test_breaking_changes_through_a_fake(self):
        self.start({"schema/schema.graphql": SCHEMA}, {"schema/schema.graphql": SCHEMA.replace("  name: String\n", "")},
                   tools=[("graphql-inspector", self.FAKE)])
        out = self.output("api-contracts")
        self.assertEqual((out["tool"], out["heuristic"], out["gaps"]), ("graphql-inspector@7.0.10", False, []))
        self.assertEqual([(s["kind"], s["reason"]) for s in out["signals"]], [
            ("graphql-inspector:breaking", "graphql-inspector breaking: Field name was removed from object type User"),
            ("graphql-inspector:dangerous", "graphql-inspector dangerous: Default value changed on argument limit")])
        self.assertValid()

    def test_a_failure_or_no_tool_falls_back_to_the_heuristic(self):
        broken = 'if "--version" in sys.argv:\n    print("7.0.10")\n    sys.exit(0)\nprint("[error] Unknown type")\nsys.exit(1)\n'
        self.start({"schema.graphql": SCHEMA}, {"schema.graphql": SCHEMA.replace("  name: String\n", "")},
                   tools=[("graphql-inspector", broken)])
        out = self.output("api-contracts")
        self.assertEqual((out["tool"], out["heuristic"]), (None, True))
        self.assertEqual(out["gaps"], ["graphql-inspector failed on `schema.graphql` ([error] Unknown type): read by the"
                                       " heuristic"])
        self.assertEqual(self.kinds("api-contracts"), [("schema.graphql", "field-removed", 3)])
        self.start({"schema.graphql": SCHEMA}, {"schema.graphql": SCHEMA.replace("  name: String\n", "")})
        self.assertIn("graphql-inspector not found on this machine: GraphQL schemas read by the heuristic only",
                      self.output("api-contracts")["gaps"])


class TestParser(unittest.TestCase):
    def test_what_the_lexer_must_not_be_fooled_by(self):
        unit = typescript.parse(
            "#!/usr/bin/env node\nimport type { A } from './a';\nconst re = /['\"{}`]/g, half = 10 / 2;\n"
            "const t = `x ${`y ${'}'}`} }`;\n/* export function commented() {} */\n"
            "export function view(): JSX.Element {\n  return (\n    <div\n      // a comment between attributes\n"
            "      title=\"it's\"\n      onClick={() => ({ a: '}' })}\n    >\n      don't {\"stop\"} <Foo.Bar x='1' />"
            "{/* } */}\n    </div>\n  );\n}\nconst id = <T,>(x: T): T => x;\n"
            "export const later = 1;\nconst lazy = import('./lazy');\nconst req = require(\"./req\");\n", "view.tsx")
        self.assertEqual(sorted(unit.exports), ["later", "view"])
        self.assertEqual(unit.exports["view"]["sigs"][0]["returns"], "JSX.Element")
        self.assertEqual(unit.imports, [("type", "./a", 2), ("dynamic", "./lazy", 19), ("require", "./req", 20)])
        with self.assertRaises(typescript.ParseError):
            typescript.parse("export const x = <T>(y: T) => y;\nconst s = 'open\n", "a.ts")

    def test_code_without_semicolons(self):
        unit = typescript.parse(
            "\ufeffexport const A = ['x'] as const\nexport const el = document.getElementById('root')!\n"
            "export function f(a: string): string\nexport function f(a: number): number\n"
            "export function f(a: any) { return a }\nexport abstract class C {\n  static K = ['x'] as const\n"
            "  cache = new Map<string, number>()\n  abstract g(): void\n  run(a: string) {}\n}\n"
            "export const b = x < y\nexport const d = e > (f)\n", "a.ts")
        self.assertEqual(sorted(unit.exports), ["A", "C", "b", "d", "el", "f"])
        self.assertEqual([typescript.sig_text(s) for s in typescript.api_sigs(unit.exports["f"]["sigs"])],
                         ["(a: string): string", "(a: number): number"])
        self.assertEqual(sorted(unit.exports["C"]["members"]), ["K", "cache", "g", "run"])

    def test_jsx_tags_count_as_references(self):
        code = typescript.strip("import { Button } from './Button'\nexport const A = () => <Select<O> x={1}>"
                                "<Button onClick={go} /><Button.Icon />don't</Select>\n", True, tags=True)[0]
        self.assertEqual((code.count("Button"), code.count("go")), (3, 1))

    def test_a_type_assertion_in_ts_is_not_jsx(self):
        unit = typescript.parse("const a = <string>value;\nexport const b = 'x';\n", "a.ts")
        self.assertEqual(list(unit.exports), ["b"])

    def test_declarations(self):
        unit = typescript.parse(
            "export function over(a: string): void;\nexport function over(a: number): void;\n"
            "export function over(a: any) {}\nexport abstract class Base<T> extends React.Component<P> {\n"
            "  static count = 0;\n  #hidden = 1;\n  protected abstract run(x: T): T;\n"
            "  constructor(private db: Db, public readonly id: string = '') { super(); }\n"
            "  get value(): number { return 1 }\n  handler = (e: Event): void => {}\n  @Input() label: string\n"
            "  render() { return null }\n}\nexport interface Props {\n  readonly a: string\n  b?: (x: number) => void;\n"
            "  c(x: string): number,\n  [key: string]: unknown\n}\nexport type U =\n  | 'a'\n  | { kind: 'b'; v: number }\n"
            "export const cache = new Map<string, number>(), other = 3\nexport { other as renamed };\n"
            "export default Base;\n", "a.ts")
        self.assertEqual(sorted(unit.exports), ["Base", "Props", "U", "cache", "default", "other", "over", "renamed"])
        self.assertEqual([typescript.sig_text(s) for s in typescript.api_sigs(unit.exports["over"]["sigs"])],
                         ["(a: string): void", "(a: number): void"])
        base = unit.exports["Base"]
        self.assertEqual((base["abstract"], base["extends"]), (True, ["React.Component"]))
        members = base["members"]
        self.assertEqual(sorted(members), ["#hidden", "constructor", "count", "db", "handler", "id", "label", "render",
                                           "run", "value"])
        self.assertEqual((members["db"]["visibility"], members["id"]["visibility"], members["run"]["abstract"]),
                         ("private", "public", True))
        self.assertEqual(typescript.sig_text(members["handler"]["sigs"][0]), "(e: Event): void")
        self.assertEqual(sorted(unit.exports["Props"]["members"]), ["[index]", "a", "b", "c"])
        self.assertEqual(unit.exports["U"]["text"], "'a'|{kind:'b',v:number}")
        self.assertEqual(unit.exports["default"]["kind"], "class")

    def test_project_resolution_and_modules(self):
        files = {"package.json": PACKAGE, "tsconfig.json": TSCONFIG, "src/a/x.ts": "", "src/b/index.tsx": "",
                 "src/c.ts": "", "components/ui/button.tsx": "", "packages/kit/package.json":
                     json.dumps({"name": "@acme/kit", "exports": {".": {"types": "./dist/index.d.ts"}}}),
                 "packages/kit/src/index.ts": "", "packages/kit/src/forms/input.ts": ""}
        project = typescript.Project(list(files), files.get)
        exists = files.__contains__
        self.assertEqual(project.resolve("src/a/x.ts", "../b", exists), "src/b/index.tsx")
        self.assertEqual(project.resolve("src/a/x.ts", "../c.js", exists), "src/c.ts", "ESM `.js` names its `.ts`")
        self.assertEqual(project.resolve("src/a/x.ts", "@/b", exists), "src/b/index.tsx")
        self.assertEqual(project.resolve("src/a/x.ts", "src/c", exists), "src/c.ts", "baseUrl")
        self.assertEqual(project.resolve("src/a/x.ts", "@acme/kit", exists), "packages/kit/src/index.ts")
        self.assertEqual(project.resolve("src/a/x.ts", "@acme/kit/forms/input", exists),
                         "packages/kit/src/forms/input.ts")
        self.assertIsNone(project.resolve("src/a/x.ts", "react", exists))
        self.assertEqual([project.module_of(p) for p in ("src/a/x.ts", "src/c.ts", "components/ui/button.tsx",
                                                          "middleware.ts", "packages/kit/src/forms/input.ts",
                                                          "packages/kit/src/index.ts")],
                         ["src/a", "src", "components", "/", "packages/kit/src/forms", "packages/kit/src"])

    def test_quick_imports(self):
        self.assertEqual(typescript.quick_imports(
            "import a from './a';\nexport { b } from \"./b\";\nimport './side.css';\nconst t = 'from ./x';\n"
            "obj.import('./no');\nconst c = await import('./c');\n", "x.ts"),
            [("value", "./a", 1), ("value", "./b", 2), ("side-effect", "./side.css", 3), ("dynamic", "./c", 6)])
        self.assertIsNone(typescript.quick_imports("const s = 'open\n", "x.ts"))


if __name__ == "__main__":
    unittest.main()
