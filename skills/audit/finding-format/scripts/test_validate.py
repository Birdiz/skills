"""Tests for validate.py: python3 -I -m unittest discover -s <this directory>"""
import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

ENGAGEMENT = "# Engagement\n\n## Target\n\ncommit: a1b2c3d4e5f6\n"

FINDING = """### F-SEC-001 Session cookie set without Secure flag

```yaml
id: F-SEC-001
axis: app-security
status: confirmed
verification: {by: sub-agent, on: 2026-10-10}
severity: medium          # critical | high | medium | low | info
confidence: high
evidence_regime: static
effort: S
resolution: open
sensitive: false
promptable: true
locations:
  - config/packages/framework.yaml:14
commit: a1b2c3d
references:
  - OWASP ASVS 5.0 3.3.1
```

**Evidence.** `config/packages/framework.yaml:14` "cookie_secure: false". Settles L-SEC-01.

**Technical explanation.** Cause, consequence.

**Plain-language explanation.** Everyday words.

**Remediation.** Set it to auto; check the header.

**Verification.** by: sub-agent, 2026-10-10. Reproduced.
"""

FINDINGS_FILE = """# app-security

## Coverage

skill: app-security@0.19.0, tools: [semgrep@1.0]

| Area | Status | Notes |
|---|---|---|
| Session | evaluated | F-SEC-001. |
| Files | partial | Waits for Q-SEC-01. |

## Findings

{finding}
## Leads

- **L-SEC-01 Cookie flags.** framework.yaml:14. Check: read it.
  promoted to F-SEC-001.
- **L-SEC-02 Upload size.** src/Upload.php:3. Check: read it. open: owner,
  Q-SEC-01.

## Questions for the auditor

- **Q-SEC-01** (Files) Which upload size? Proposal: 5 MB (src/Upload.php:3).
  **Answer (2026-10-11, owner):** "5 MB" accepts the proposal: 5 MB.
"""

PLAN = """# Remediation plan
commit: a1b2c3d4e5f6
skill: remediation-plan@0.19.0
tools: [python3@3.9.6]
findings: 1 confirmed open, from findings/*.md read on 2026-10-12
generated: 2026-10-12

## Order
| # | Fix | Title | Severity | Effort | Executor | Waits for | Quick win |
|---|---|---|---|---|---|---|---|
| 1 | R-001 | Secure the session cookie | medium | S | code | — | yes |

## Fixes

### R-001 Secure the session cookie

```yaml
id: R-001
findings: [F-SEC-001]
grouping: single
status: open
severity: medium
effort: S
executor: code
promptable: true
sensitive: false
waits_for: []
locations:
  - config/packages/framework.yaml:14
```

**Grouping.** Alone.

**Change.** Cookie secure.

**Check.** F-SEC-001: the header carries Secure.

## Discrepancies

None.
"""


class ValidateTest(unittest.TestCase):
    def workspace(self, finding=FINDING, findings_file=FINDINGS_FILE, plan=PLAN, extra=None):
        root = tempfile.mkdtemp()
        os.mkdir(os.path.join(root, "findings"))
        files = {"00-engagement.md": ENGAGEMENT,
                 "findings/app-security.md": findings_file.replace("{finding}", finding)}
        if plan is not None:
            files["02-remediation-plan.md"] = plan
        files.update(extra or {})
        for name, text in files.items():
            with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        return root

    def run_on(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = validate.main(["validate.py", root] + list(args))
        return code, out.getvalue()

    def assertFlags(self, kind, needle, **kw):
        args = kw.pop("args", ())
        code, out = self.run_on(self.workspace(**kw), *args)
        lines = [l for l in out.splitlines() if l.startswith(kind) and needle in l]
        self.assertTrue(lines, "no %s line with %r in:\n%s" % (kind, needle, out))
        return code, out

    def test_valid_workspace(self):
        code, out = self.run_on(self.workspace(), "--require", "verification", "--require", "plan")
        self.assertEqual(code, 0, out)
        self.assertIn("errors 0, warnings 0, pending 0", out)

    def test_yaml_value_outside_enum(self):
        self.assertFlags("ERROR", "severity `severe`", finding=FINDING.replace("severity: medium", "severity: severe"))

    def test_missing_key(self):
        self.assertFlags("ERROR", "key `effort` missing", finding=FINDING.replace("effort: S\n", ""))

    def test_heading_and_id_differ(self):
        self.assertFlags("ERROR", "differs from the heading", finding=FINDING.replace("id: F-SEC-001", "id: F-SEC-002"))

    def test_wrong_axis_code(self):
        self.assertFlags("ERROR", "F-SEC-<NNN>", finding=FINDING.replace("F-SEC-001", "F-QUA-001"))

    def test_missing_prose_section(self):
        self.assertFlags("ERROR", "**Plain-language explanation.** missing",
                         finding=FINDING.replace("**Plain-language explanation.** Everyday words.\n", ""))

    def test_confirmed_without_note(self):
        self.assertFlags("ERROR", "without a **Verification.** note",
                         finding=FINDING.replace("**Verification.** by: sub-agent, 2026-10-10. Reproduced.\n", ""))

    def test_unverified_is_pending_then_required(self):
        finding = (FINDING.replace("status: confirmed", "status: unverified")
                   .replace("verification: {by: sub-agent, on: 2026-10-10}\n", "")
                   .replace("**Verification.** by: sub-agent, 2026-10-10. Reproduced.\n", ""))
        code, _ = self.assertFlags("PENDING verify-findings", "not verified yet", finding=finding)
        self.assertEqual(code, 0)
        code, _ = self.assertFlags("ERROR", "not verified yet", finding=finding, args=("--require", "verification"))
        self.assertEqual(code, 1)

    def test_answer_after_verification(self):
        finding = FINDING + "\n**Auditor answer.** Q-SEC-01, answer 2026-10-11: severity kept.\n"
        self.assertFlags("PENDING verify-findings", "auditor answer 2026-10-11 after verification 2026-10-10",
                         finding=finding)

    def test_accepted_without_answer(self):
        self.assertFlags("ERROR", "resolution accepted without",
                         finding=FINDING.replace("resolution: open", "resolution: accepted"), plan=None)

    def test_lead_without_status(self):
        self.assertFlags("ERROR", "L-SEC-02: no status",
                         findings_file=FINDINGS_FILE.replace(" open: owner,\n  Q-SEC-01.", "\n  Q-SEC-01."))

    def test_lead_promoted_to_unknown_finding(self):
        self.assertFlags("ERROR", "points to F-SEC-009",
                         findings_file=FINDINGS_FILE.replace("promoted to F-SEC-001", "promoted to F-SEC-009"))

    def test_area_status(self):
        self.assertFlags("ERROR", "status `done`", findings_file=FINDINGS_FILE.replace("| partial |", "| done |"))

    def test_answer_form(self):
        self.assertFlags("ERROR", "Q-SEC-01: answer not",
                         findings_file=FINDINGS_FILE.replace("**Answer (2026-10-11, owner):**", "**Answer 2026-10-11:**"))

    def test_lead_for_other_axis_waits_for_move(self):
        text = FINDINGS_FILE.replace("## Questions for the auditor",
                                     "## Leads for other axes\n\n- **privacy: Cookie scope.** framework.yaml:9.\n\n"
                                     "## Questions for the auditor")
        self.assertFlags("PENDING verify-findings", "lead for privacy not moved", findings_file=text)

    def test_sections_out_of_order(self):
        text = FINDINGS_FILE.replace("## Coverage", "## Leads-tmp").replace("## Leads\n", "## Coverage\n")
        text = text.replace("## Leads-tmp", "## Leads")
        self.assertFlags("ERROR", "sections out of order", findings_file=text)

    def test_plan_severity_follows_findings(self):
        self.assertFlags("ERROR", "R-001: severity low, its findings give medium",
                         plan=PLAN.replace("severity: medium", "severity: low").replace("| medium |", "| low |"))

    def test_plan_missing_finding_is_pending(self):
        plan = PLAN.replace("findings: [F-SEC-001]", "findings: []").replace("status: open", "status: dropped")
        self.assertFlags("PENDING remediation-plan", "in no open fix", plan=plan)

    def test_plan_stale(self):
        self.assertFlags("PENDING remediation-plan", "after the plan",
                         plan=PLAN.replace("generated: 2026-10-12", "generated: 2026-10-09"))

    def test_plan_quick_win_derived(self):
        self.assertFlags("ERROR", "quick win `no`, derived yes", plan=PLAN.replace("| yes |", "| no |"))

    def test_plan_waits_for_unknown_fix(self):
        plan = PLAN.replace("waits_for: []", "waits_for: [R-007]").replace("| — | yes |", "| R-007 | no |")
        self.assertFlags("ERROR", "waits for unknown fix R-007", plan=plan)

    def test_plan_order_row_differs(self):
        self.assertFlags("ERROR", "`## Order` effort `M`", plan=PLAN.replace("| medium | S |", "| medium | M |"))

    def test_no_plan_with_confirmed_findings(self):
        self.assertFlags("ERROR", "no plan yet", plan=None, args=("--require", "plan"))

    def test_unreadable_workspace(self):
        code, _ = self.run_on(tempfile.mkdtemp())
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
