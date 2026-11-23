"""Tests for risk_map.py: python3 -I -m unittest discover -s <this directory>"""
import os
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import risk_map  # noqa: E402


def matches(glob, path):
    return risk_map.compile_glob(glob)(path)


class TestGlob(unittest.TestCase):
    def test_star_stays_in_one_segment(self):
        self.assertTrue(matches("src/*.php", "src/Kernel.php"))
        self.assertFalse(matches("src/*.php", "src/Security/Voter.php"))

    def test_double_star_spans_segments(self):
        self.assertTrue(matches("src/Security/**", "src/Security/Voter.php"))
        self.assertTrue(matches("src/Security/**", "src/Security/Auth/Login.php"))
        self.assertFalse(matches("src/Security/**", "src/SecurityBundle.php"))
        self.assertTrue(matches("**/Billing/*.php", "src/Billing/Charge.php"))
        self.assertTrue(matches("**/Billing/*.php", "Billing/Charge.php"))
        self.assertTrue(matches("src/**/Charge.php", "src/Charge.php"))
        self.assertTrue(matches("src/**/Charge.php", "src/a/b/Charge.php"))

    def test_a_glob_without_a_slash_matches_a_name_at_any_depth(self):
        self.assertTrue(matches("*.sql", "db/migrations/001.sql"))
        self.assertTrue(matches("migrations", "db/migrations/001.sql"))
        self.assertTrue(matches("migrations/", "db/migrations/001.sql"))
        self.assertFalse(matches("migrations/", "src/migrations"))  # a file, not a directory

    def test_a_glob_with_a_slash_is_anchored_at_the_root(self):
        self.assertTrue(matches("src/Security", "src/Security/Voter.php"))
        self.assertFalse(matches("src/Security", "lib/src/Security/Voter.php"))
        self.assertTrue(matches("/Makefile", "Makefile"))
        self.assertFalse(matches("/Makefile", "sub/Makefile"))

    def test_question_mark_and_classes(self):
        self.assertTrue(matches("v?/api.yaml", "v1/api.yaml"))
        self.assertFalse(matches("v?/api.yaml", "v10/api.yaml"))
        self.assertTrue(matches("v[12]/api.yaml", "v2/api.yaml"))
        self.assertFalse(matches("v[!12]/api.yaml", "v2/api.yaml"))

    def test_dots_and_special_characters_are_literal(self):
        self.assertFalse(matches("a.b", "axb"))
        self.assertTrue(matches("routes+(x).php", "routes+(x).php"))

    def test_malformed_globs_are_rejected(self):
        for glob in ("", " a", "!src/**", "a|b", "src\\a", "../x", "/", "a[b", "a]b["):
            with self.subTest(glob=glob):
                self.assertIsNotNone(risk_map.glob_problem(glob))
                with self.assertRaises(risk_map.GlobError):
                    risk_map.compile_glob(glob)


class TestFile(unittest.TestCase):
    ROWS = [("src/Security/**", "auth"), ("migrations/", "irreversible"), ("*.graphql", "public-api")]

    def test_render_then_parse_round_trips(self):
        text = risk_map.render(["php", "typescript"], self.ROWS)
        stacks, rows, problems = risk_map.parse(text)
        self.assertEqual(problems, [])
        self.assertEqual(stacks, ["php", "typescript"])
        self.assertEqual([(g, z) for g, z, _ in rows], self.ROWS)

    def test_render_holds_only_repo_facts(self):
        text = risk_map.render(["php"], self.ROWS)
        self.assertNotRegex(text, r"\d+\.\d+\.\d+")    # no tool or skill versions
        self.assertNotIn("state", text)                 # no run root
        self.assertNotRegex(text, r"\d{4}-\d{2}-\d{2}")  # no date
        self.assertIn("| `src/Security/**` | auth |", text)

    def test_an_empty_risk_map_parses(self):
        stacks, rows, problems = risk_map.parse(risk_map.render([], []))
        self.assertEqual((stacks, rows, problems), ([], [], []))

    def test_hand_edits_parse_and_bad_rows_are_reported(self):
        text = ("# Review\n\n## Stacks\n\n- PHP\n* `python`\n\n## Risk map\n\n"
                "| Glob | Zone |\n|:---|---|\n| src/Pay/** | payments |\n| `!x` | auth |\n"
                "| a/** | Bad Zone |\n| a | b | c |\n")
        stacks, rows, problems = risk_map.parse(text)
        self.assertEqual(stacks, ["php", "python"])
        self.assertEqual([(g, z) for g, z, _ in rows], [("src/Pay/**", "payments")])
        self.assertEqual([n for n, _ in problems], [13, 14, 15])

    def test_missing_sections_are_reported(self):
        _, _, problems = risk_map.parse("# Review\n")
        self.assertEqual([m for _, m in problems], ["no `## Stacks` section", "no `## Risk map` section"])

    def test_zones_for_names_each_zone_once_with_its_glob(self):
        rows = [("src/Security/**", "auth"), ("src/**/Login*.php", "auth"), ("src/Security/Pay*", "payments")]
        self.assertEqual(risk_map.zones_for("src/Security/PayVoter.php", rows),
                         [("auth", "src/Security/**"), ("payments", "src/Security/Pay*")])
        self.assertEqual(risk_map.zones_for("src/Kernel.php", rows), [])


if __name__ == "__main__":
    unittest.main()
