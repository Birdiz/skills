"""Tests for the structure step's files, files in and files out:
python3 -I -m unittest discover -s <this directory>

Each test builds a repository whose branch adds a module, a layer, an
entry point, a dependency beside one of the same category, and new type
names, with or without a glossary and ADRs. A run writes the structure
detector's output and the worksheet; the tests fill the worksheet as the
step would, regenerate the brief, and check the run with validate.py and
check-pointers.py. The step's judgment itself is not tested here: only
what the files must say. The TypeScript adapter graphs these repositories,
with no edge between modules; a graph with edges is injected into the run
directory in the stack-neutral format.
"""
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "core"))
from test_run import GIT, Fixture, check, entry, git, read, write  # noqa: E402
import contracts  # noqa: E402
import pocock  # noqa: E402
import review_format as fmt  # noqa: E402
import structure  # noqa: E402

GLOSSARY = """# Shop

## Language

**Customer**:
A person who places orders.
_Avoid_: Client, buyer

**Invoice**:
A request for payment sent after delivery.
_Avoid_: Bill
"""
DOMAIN = """# Domain Docs

- **`GLOSSARY.md`** at the repo root, or
- **`GLOSSARY-MAP.md`** at the repo root if it exists.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.
"""
ADR = "# Billing talks to Ordering through events\n\nBilling never calls Ordering directly.\n"
PACKAGE = '{\n  "dependencies": {\n    "axios": "^1.6.0"\n  }\n}\n'
PACKAGE_HEAD = '{\n  "dependencies": {\n    "axios": "^1.6.0",\n    "got": "^14.0.0"\n  }\n}\n'
BASE = {"package.json": PACKAGE, "src/ordering/order.ts": "export class Order {}\n",
        "src/ordering/http/client.ts": "import axios from 'axios';\nexport const http = axios.create();\n"}
HEAD = {"package.json": PACKAGE_HEAD,
        "src/billing/batch.ts": "export class InvoiceBatch {}\nexport class CustomerRepository {}\n",
        "src/ordering/projections/totals.ts": "export class Bill {}\n",
        "src/ordering/OrderController.ts": "export class OrderController {}\n",
        "src/ordering/order.ts": "export class Order {}\nexport interface RetryPolicy {}\n"}
WITH_DOCS = {"GLOSSARY.md": GLOSSARY, "docs/agents/domain.md": DOMAIN, "docs/adr/0001-events.md": ADR}
AREAS = structure.AREAS


def finding(n, diff, locations, evidence, title, attention="glance", blocks="false"):
    return """### F-STR-%03d %s

```yaml
id: F-STR-%03d
axis: structure
status: unverified
severity: medium
confidence: high
sensitive: false
promptable: true
locations:
%s
diff: %s
attention: %s
blocks_merge: %s
fan_in: unknown
```

**Evidence.** %s

**Reviewer question.** Should this go through what the codebase already has?
""" % (n, title, n, "\n".join("  - %s" % loc for loc in locations), diff, attention, blocks, evidence)


def fill(sheet, rows, findings=(), axis="evaluated"):
    """The structure worksheet as the step fills it: `rows` maps a row ID to
    its cells after the first ((needed, why, finding) for a dependency,
    (judgment, finding) otherwise)."""
    out, section = [], None
    for line in sheet.split("\n"):
        if line.startswith("## "):
            section = line[3:]
        if section == "Coverage" and "| not-evaluable | Step not run yet" in line:
            line = "| %s | %s | |" % (line.split("|")[1].strip(), axis)
        elif line.startswith("Axis: "):
            line = "Axis: %s" % axis
        elif section in structure.SECTIONS and line[:3] in ("| D", "| T", "| G"):
            rid = line[2:].split(" ", 1)[0]
            if rid in rows:
                tail = "| ? | ? | |" if section == "Dependencies" else "| ? | |"
                line = line[:line.rindex(tail)] + "| %s |" % " | ".join(rows[rid])
        out.append(line)
    text = "\n".join(out)
    if findings:
        text = text.replace("## Findings\n\nNone.\n", "## Findings\n\n" + "\n".join(findings))
    return text


def graph(base_edges, head_edges, modules):
    side = lambda edges: {"modules": modules, "edges": [{"from": a, "to": b, "line": n} for a, b, n in edges]}
    return {"base": side(base_edges), "head": side(head_edges)}


class TestGraphFormat(unittest.TestCase):
    MODS = {"a.php": "A", "b.php": "B", "c.php": "C", "a2.php": "A"}

    def test_new_cross_module_edges_and_cycles(self):
        new, cycles = structure.graph_diff(graph(
            [("a.php", "b.php", 1)],
            [("a.php", "b.php", 1), ("b.php", "c.php", 2), ("c.php", "a.php", 3), ("a.php", "a2.php", 4)],
            self.MODS))
        self.assertEqual([(e["from"], e["to"]) for e in new], [("B", "C"), ("C", "A")])
        self.assertEqual([c["modules"] for c in cycles], [["A", "B", "C"]])
        self.assertEqual(cycles[0]["via"][0]["from"], "b.php")

    def test_a_cycle_the_base_had_is_not_new(self):
        edges = [("a.php", "b.php", 1), ("b.php", "a.php", 2)]
        new, cycles = structure.graph_diff(graph(edges, edges + [("a2.php", "b.php", 3)], self.MODS))
        self.assertEqual((new, cycles), ([], []))

    def test_an_edge_to_a_file_with_no_module_is_left_out(self):
        new, _ = structure.graph_diff(graph([], [("a.php", "vendor/x.php", 1)], self.MODS))
        self.assertEqual(new, [])

    def test_the_adapter_output_signals_the_importing_file(self):
        out = structure.graph_output("import-graph-php", "x", graph([], [("a.php", "b.php", 7)], self.MODS), "php")
        self.assertEqual(out["signals"], [{"path": "a.php", "kind": "import-edge-added", "line": 7,
                                           "reason": "new import from module `A` to module `B` (`b.php`)"}])
        with self.assertRaises(ValueError):
            structure.graph_output("deptrac", "x", {}, "php")


class TestPocockGlossary(unittest.TestCase):
    def test_terms_and_avoided_words_in_both_shapes(self):
        terms = pocock.glossary_terms(GLOSSARY + "\n- **Review run**: one review.\n  _Avoid_: pass\n")
        self.assertEqual([(t["term"], t["avoid"]) for t in terms],
                         [("Customer", ["Client", "buyer"]), ("Invoice", ["Bill"]), ("Review run", ["pass"])])
        self.assertEqual(terms[0]["line"], 5)

    def test_the_map_lists_its_glossaries(self):
        self.assertEqual(pocock.glossary_map("- [Ordering](./src/ordering/GLOSSARY.md): orders\n"
                                             "- [Billing](src/billing/GLOSSARY.md): invoices\n"),
                         ["src/ordering/GLOSSARY.md", "src/billing/GLOSSARY.md"])

    def test_the_domain_doc_names_what_the_review_reads(self):
        doc = pocock.domain_doc(DOMAIN)
        self.assertEqual((doc["names_glossary"], doc["names_map"], doc["adr_dirs"]), (True, False, ["docs/adr"]))
        self.assertTrue(pocock.domain_doc(DOMAIN, map_exists=True)["names_map"])
        doc = pocock.domain_doc("Read `CONTEXT.md` first.\n")
        self.assertEqual(doc["glossary_drift"][0], "names legacy CONTEXT.md; the review reads GLOSSARY.md /"
                                                   " GLOSSARY-MAP.md")
        self.assertEqual(doc["adr_drift"], ["names no ADR directory (e.g. docs/adr/)"])


@unittest.skipIf(GIT is None, "git is not installed")
class TestStructure(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(self)

    def build(self, base, head):
        """`main` gains `base`, and `feature/x` is cut from it again with `head`."""
        fx = self.fx
        git(fx.repo, "checkout", "-q", "main")
        for rel, text in base.items():
            write(fx.repo, rel, text)
        git(fx.repo, "add", "-A")
        fx.base = git(fx.repo, "commit", "-qm", "base files")
        git(fx.repo, "branch", "-q", "-D", "feature/x")
        git(fx.repo, "checkout", "-qb", "feature/x")
        for rel, text in head.items():
            write(fx.repo, rel, text)
        git(fx.repo, "add", "-A")
        fx.head = git(fx.repo, "commit", "-qm", "head files")
        git(fx.repo, "checkout", "-q", "main")

    def start(self, base=None, head=None):
        self.build(dict(BASE, **(WITH_DOCS if base is None else base)), HEAD if head is None else head)
        code, root, out = self.fx.run("feature/x", "--no-spec")
        self.assertEqual(code, 0, out)
        self.root, self.out = root, out
        self.diff = json.loads(read(os.path.join(root, "run.json")))["diff"]
        self.so = json.loads(read(os.path.join(root, "signals", "structure.json")))
        self.blank = self.sheet()
        return root

    def sheet(self):
        return read(os.path.join(self.root, "findings", "structure.md"))

    def write(self, text):
        with open(os.path.join(self.root, "findings", "structure.md"), "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out = entry("brief.py", self.root)
        self.assertEqual(code, 0, out)
        return out

    def brief(self):
        return read(os.path.join(self.root, "brief.md"))

    def assertRunOK(self):
        code, report = check(self.root, "--require", "brief", "--require", "structure")
        self.assertEqual(code, 0, report)
        self.assertIn("errors 0, warnings 0", report)
        code, report = entry("check-pointers.py", self.root)
        self.assertEqual(code, 0, report)

    def errors(self, text):
        self.write(text)
        code, report = check(self.root, "--require", "brief", "--require", "structure")
        self.assertEqual(code, 1, report)
        return report

    def got(self, n=1):
        return finding(n, self.diff, ["package.json:4", "src/ordering/http/client.ts:1"],
                       '`package.json:4` "^14.0.0" adds got, while `src/ordering/http/client.ts:1`'
                       ' "import axios from \'axios\';" is how the codebase calls HTTP.', "A second HTTP client")

    def batch(self, n=2):
        return finding(n, self.diff, ["src/billing/batch.ts:1", "GLOSSARY.md:5"],
                       '`src/billing/batch.ts:1` "export class InvoiceBatch {}" names a concept `GLOSSARY.md:5`'
                       ' "**Customer**:" and its neighbours do not define.', "InvoiceBatch is not in the glossary")

    def good(self):
        return fill(self.blank, {"D1": ("not needed", "axios already calls HTTP", "F-STR-001"),
                                 "T1": ("domain term", "F-STR-002"), "T2": ("not a domain term", ""),
                                 "T3": ("domain term", "F-STR-002")},
                    findings=[self.got(), self.batch()])

    # --- the detector -------------------------------------------------------------------

    def test_new_files_are_classified_by_path(self):
        self.start()
        classes = {f["path"]: (f["class"], f["new_module"]) for f in self.so["new_files"]}
        self.assertEqual(classes, {
            "src/billing/batch.ts": ("module", True),
            "src/ordering/projections/totals.ts": ("layer", False),
            "src/ordering/OrderController.ts": ("entry point", False),
        })
        self.assertEqual(self.so["new_modules"], ["src/billing"])
        self.assertEqual(self.so["signals"], [], "classes are no signal: git-changes already signals new files")

    def test_a_new_dependency_names_its_category_and_peers(self):
        self.start()
        self.assertEqual(self.so["dependencies"], [{
            "did": "D1", "path": "package.json", "name": "got", "spec": "^14.0.0 (dependencies)", "line": 4,
            "category": "http-client", "peers": ["axios"]}])
        self.assertIn("| D1 `package.json:4` `got` ^14.0.0 (dependencies), http-client, beside `axios` | ? | ? | |",
                      self.blank)

    def test_type_names_no_glossary_term_names_get_a_row(self):
        self.start()
        self.assertEqual([(t["tid"], t["name"], t.get("note")) for t in self.so["terms"]], [
            ("T1", "InvoiceBatch", None),
            ("T2", "RetryPolicy", None),
            ("T3", "Bill", "the glossary says to avoid `bill`: use **Invoice**")])
        self.assertEqual([(k["name"], k["term"]) for k in self.so["known_terms"]], [("CustomerRepository", "Customer")])
        self.assertNotIn("OrderController", self.blank, "Order is in the code at the base: not a new term")
        self.assertEqual(self.so["domain"]["adrs"]["dirs"], [{"path": "docs/adr", "files": ["docs/adr/0001-events.md"]}])

    # --- the worksheet and the step --------------------------------------------------------

    def test_the_worksheet_is_pending_until_the_step_runs(self):
        self.start()
        self.assertIn("STEP: structure %s" % os.path.join(os.path.dirname(HERE), "steps", "structure.md"), self.out)
        self.assertLess(self.out.index("STEP: contracts"), self.out.index("STEP: structure"))
        self.assertIn("| Import graph | not-evaluable | Step not run yet", self.blank,
                      "the TypeScript adapter supplies the graph: the step judges the area")
        self.assertIn("## Imports\n\nNone.\n", self.blank)
        code, report = check(self.root, "--require", "brief")
        self.assertEqual(code, 0, report)
        self.assertIn("PENDING structure", report)
        code, report = check(self.root, "--require", "brief", "--require", "structure")
        self.assertEqual(code, 1, report)
        self.assertIn("the structure step has not run", report)
        top = self.brief().split("## New structure\n\n")[1].split("## ")[0]
        self.assertIn("- New modules: `src/billing/` (1 file(s)).", top)
        self.assertIn("- Layer: `src/ordering/projections/totals.ts`.", top)
        self.assertIn("- Entry point: `src/ordering/OrderController.ts`.", top)
        self.assertIn("- New dependency `package.json:4` `got` ^14.0.0 (dependencies), http-client, beside `axios`:"
                      " not judged: the structure step did not run.", top)
        self.assertIn("- Import graph (signals/import-graph-typescript.json, heuristic): 0 new cross-module edge(s),"
                      " 0 new cycle(s).", top)
        self.assertIn("- Glossary: 2 term(s) in GLOSSARY.md; 3 new type name(s) no term names.", top)
        self.assertIn("- ADRs: 1 ADR(s) in docs/adr/.", top)
        gaps = self.brief().split("## Coverage gaps")[1]
        self.assertNotIn("structure, Import graph", gaps)

    def test_a_filled_worksheet_passes_and_shows_in_the_brief(self):
        self.start()
        out = self.write(self.good())
        self.assertIn("Proposed verdict: merge, round 1 (intent not checked:", out)
        self.assertNotIn(" structure,", out.split("(")[1])
        self.assertRunOK()
        brief = self.brief()
        self.assertIn("http-client, beside `axios`: not needed: axios already calls HTTP (F-STR-001).", brief)
        self.assertIn("3 new type name(s) no term names, 2 judged a domain term (F-STR-002).", brief)
        self.assertIn("- Structure: 3 new file(s), 1 new module(s); 1 new dependency(ies), 1 not needed; 3 new type"
                      " name(s) outside the glossary, 2 judged a domain term; 0 import change(s), 0 across a"
                      " boundary.",
                      brief.split("## Verdict")[1])
        self.assertIn("F-STR-001 A second HTTP client", brief.split("## Glance")[1].split("## ")[0])

    def test_the_rows_are_checked_against_the_detector(self):
        self.start()
        report = self.errors(fill(self.blank, {"D1": ("not needed", "?", ""), "T1": ("domain term", ""),
                                               "T2": ("maybe", ""), "T3": ("not a domain term", "F-STR-009")}))
        for message in ("D1: say why it looks not needed", "D1 (not needed) needs the finding that says why",
                        "T1 (domain term) needs the finding that says why",
                        "T2: judgment `maybe` not in domain term | not a domain term",
                        "T3 cites F-STR-009, which is not a finding of this file"):
            self.assertIn(message, report)
        sheet = self.blank.replace("| T3 `src/ordering/projections/totals.ts", "| T3 `src/other.ts")
        sheet = sheet.replace("| T1 ", "| T7 ")
        report = self.errors(fill(sheet, {"D1": ("needed", "used", ""), "T2": ("not a domain term", ""),
                                          "T3": ("not a domain term", ""), "T7": ("not a domain term", "")}))
        for message in ("T7 is not a row of `## Terms` in this run", "T1 has no row in `## Terms`",
                        "T3 is about `src/ordering/projections/totals.ts`, not what this row names"):
            self.assertIn(message, report)

    def test_the_areas_fixed_by_the_run_stay_fixed(self):
        self.start(base={})
        text = self.good().replace("| Glossary | not-evaluable (no glossary) |", "| Glossary | evaluated |")
        text = text.replace("| Import graph | evaluated |", "| Import graph | not-evaluable (no glossary) |")
        report = self.errors(text)
        self.assertIn("area `Glossary` is `not-evaluable (no glossary)` in this run, fixed by what exists: not"
                      " `evaluated`", report)
        self.assertIn("area `Import graph` is evaluable in this run: judge it, or say `partial (<what>)`", report)

    def test_the_tables_belong_to_the_structure_file(self):
        self.start()
        path = os.path.join(self.root, "findings", "contracts.md")
        write(os.path.dirname(path), "contracts.md", read(path).replace("## Findings", "## Terms\n\nNone.\n\n## Findings"))
        code, report = check(self.root)
        self.assertIn("`## Terms` belongs to the structure findings file", report)

    # --- no glossary, no ADRs, drift ---------------------------------------------------------

    def test_no_glossary_and_no_adrs_are_not_evaluable_not_drift(self):
        self.start(base={})
        self.assertEqual(self.so["areas"], {"Glossary": "not-evaluable (no glossary)",
                                            "ADRs": "not-evaluable (no ADRs)"})
        self.assertEqual(self.so["domain"]["doc"]["status"], "missing")
        self.assertIn("## Terms\n\nNone.\n", self.blank)
        self.write(fill(self.blank, {"D1": ("not needed", "axios already calls HTTP", "F-STR-001")},
                        findings=[self.got()]))
        self.assertRunOK()
        top = self.brief().split("## New structure")[1].split("## ")[0]
        self.assertIn("- Glossary: not-evaluable (no glossary).", top)
        self.assertIn("- ADRs: not-evaluable (no ADRs).", top)

    def test_a_drifted_domain_doc_makes_its_areas_not_evaluable(self):
        self.start(base={"GLOSSARY.md": GLOSSARY, "docs/agents/domain.md": "Read `CONTEXT.md` and `docs/adr/`.\n",
                         "docs/adr/0001-events.md": ADR})
        self.assertEqual(self.so["areas"]["Glossary"], "not-evaluable (contract drift: domain doc, names legacy"
                                                       " CONTEXT.md; the review reads GLOSSARY.md / GLOSSARY-MAP.md;"
                                                       " names no GLOSSARY.md or GLOSSARY-MAP.md)")
        self.assertNotIn("ADRs", self.so["areas"])
        self.assertEqual(self.so["terms"], [])

    def test_a_glossary_map_names_the_glossaries_and_context_adrs(self):
        base = {"GLOSSARY-MAP.md": "# Glossary Map\n\n## Contexts\n\n- [Billing](./src/billing/GLOSSARY.md): bills\n",
                "docs/agents/domain.md": DOMAIN + "- `src/<context>/docs/adr/` for context decisions.\n",
                "src/billing/GLOSSARY.md": "# Billing\n\n**Invoice batch**:\nInvoices sent together.\n",
                "src/billing/docs/adr/0001-batches.md": ADR}
        self.start(base=base)
        self.assertEqual(self.so["domain"]["glossary"]["map"], "GLOSSARY-MAP.md")
        self.assertEqual([k["name"] for k in self.so["known_terms"]], ["InvoiceBatch"])
        self.assertIn({"path": "src/billing/docs/adr", "files": ["src/billing/docs/adr/0001-batches.md"]},
                      self.so["domain"]["adrs"]["dirs"])

    # --- an import graph, as an adapter will write it -------------------------------------------

    def test_an_adapter_graph_gets_rows_and_stays_out_of_contracts(self):
        self.start()
        mods = {"src/ordering/order.ts": "src/ordering", "src/billing/batch.ts": "src/billing"}
        out = structure.graph_output("import-graph-ts", fmt.VERSION, graph(
            [], [("src/billing/batch.ts", "src/ordering/order.ts", 1),
                 ("src/ordering/order.ts", "src/billing/batch.ts", 2)], mods), "ts")
        rel = "signals/import-graph-ts.json"
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            json.dump(out, fh)
        header = json.loads(read(os.path.join(self.root, "run.json")))
        header["detectors"].append(rel)
        with open(os.path.join(self.root, "run.json"), "w", encoding="utf-8") as fh:
            json.dump(header, fh)
        run = fmt.Run(self.root)
        outputs = [(r, o) for r, o in run.outputs.items() if o.get("detector") != "git-changes"]
        self.assertEqual([r for r in contracts.signal_rows(outputs) if r["detector"] == "import-graph-ts"], [],
                         "a new import is not a contract signal")
        so = dict(run.structure_output(), areas={k: v for k, v in run.structure_output()["areas"].items()
                                                  if k != "Import graph"}, import_graphs=["import-graph-ts"])
        with open(os.path.join(self.root, "signals", "structure.json"), "w", encoding="utf-8") as fh:
            json.dump(so, fh)
        sheet = fmt.findings_at_start("structure", None, run.changed(), [(r, o if r != "signals/structure.json" else so)
                                                                          for r, o in outputs])
        self.assertIn("| G1 `src/billing/batch.ts:1` import-graph-ts edge `src/billing` -> `src/ordering` | ? | |", sheet)
        self.assertIn("| G2 `src/ordering/order.ts:2` import-graph-ts edge `src/ordering` -> `src/billing` | ? | |", sheet)
        self.assertIn("| G3 `src/billing/batch.ts:1` import-graph-ts cycle `src/billing`, `src/ordering` | ? | |", sheet)
        rows = {"D1": ("needed", "used", ""), "T1": ("not a domain term", ""), "T2": ("not a domain term", ""),
                "T3": ("not a domain term", ""), "G1": ("fits", ""), "G2": ("boundary", ""), "G3": ("fits", "")}
        report = self.errors(fill(sheet, rows))
        self.assertIn("G2 (boundary) needs the finding that says why", report)
        cycle = finding(1, self.diff, ["src/ordering/order.ts:2"], '`src/ordering/order.ts:2` "export interface'
                        ' RetryPolicy {}" sits where Ordering starts importing Billing.', "Ordering imports Billing",
                        attention="must-read", blocks="true")
        rows["G2"] = ("boundary", "F-STR-001")
        self.write(fill(sheet, rows, findings=[cycle]))
        self.assertRunOK()
        top = self.brief().split("## New structure")[1].split("## ")[0]
        self.assertIn("- Import graph (signals/import-graph-ts.json, heuristic): 2 new cross-module edge(s),"
                      " 1 new cycle(s).", top)
        self.assertIn("3 import change(s), 1 across a boundary",
                      self.brief().split("## Verdict")[1])


if __name__ == "__main__":
    unittest.main()
