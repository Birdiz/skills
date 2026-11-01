"""Tests for validate.py: python3 -I -m unittest discover -s <this directory>"""
import contextlib
import io
import os
import re
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

skill: app-security@0.20.0, tools: [semgrep@1.0]

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
skill: remediation-plan@0.20.0
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

    def sha(self, finding=FINDING, fid="F-SEC-001"):
        out = self.run_on(self.workspace(finding=finding, plan=None), "--fingerprint", fid)[1]
        return out.split()[1]

    def stamped(self, finding=FINDING):
        return re.sub(r"(verification: \{by: sub-agent, on: [\d-]+)\}", r"\1, sha: %s}" % self.sha(finding), finding)

    def sourced(self, finding=FINDING, plan=PLAN):
        return plan.replace("waits_for: []", "waits_for: []\nsources: {F-SEC-001: %s}" % self.sha(finding))

    def test_valid_workspace(self):
        finding = self.stamped()
        code, out = self.run_on(self.workspace(finding=finding, plan=self.sourced(finding)),
                                "--require", "verification", "--require", "plan")
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

    def test_answer_rechecked_without_change(self):
        finding = (FINDING.replace("Reproduced.\n", "Reproduced.\nRe-checked 2026-10-12, answer of 2026-10-11: no change.\n")
                   + "\n**Auditor answer.** Q-SEC-01, answer 2026-10-11: severity kept.\n")
        code, out = self.run_on(self.workspace(finding=finding), "--require", "verification")
        self.assertNotIn("after verification", out)
        self.assertEqual(code, 0, out)

    def test_recheck_in_its_own_paragraph(self):
        finding = (FINDING + "\nRe-checked 2026-10-12, answer of 2026-10-11: no change.\n"
                   + "\n**Auditor answer.** Q-SEC-01, answer 2026-10-11: severity kept.\n")
        code, out = self.run_on(self.workspace(finding=finding), "--require", "verification")
        self.assertEqual(code, 0, out)

    def test_recheck_of_another_answer_still_pending(self):
        finding = (FINDING.replace("Reproduced.\n", "Reproduced.\nRe-checked 2026-10-12, answer of 2026-10-09: no change.\n")
                   + "\n**Auditor answer.** Q-SEC-01, answer 2026-10-11: severity kept.\n")
        self.assertFlags("PENDING verify-findings", "auditor answer 2026-10-11", finding=finding)

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

    def test_asked_form_without_id(self):
        text = FINDINGS_FILE + "- Which host? **Asked 2026-10-12, not answered**\n"
        code, out = self.assertFlags("ERROR", "question: not `**Asked", findings_file=text)
        self.assertIn("2 questions", out)

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

    def test_plan_same_files_mixes_sensitivity(self):
        finding2 = (FINDING.replace("F-SEC-001", "F-SEC-002").replace("sensitive: false", "sensitive: true")
                    .replace("Settles L-SEC-01.", ""))
        plan = (PLAN.replace("findings: [F-SEC-001]", "findings: [F-SEC-001, F-SEC-002]")
                .replace("grouping: single", "grouping: same-files").replace("sensitive: false", "sensitive: true"))
        self.assertFlags("ERROR", "mixes sensitive and non-sensitive", finding=FINDING + "\n" + finding2, plan=plan)

    def test_plan_location_in_workspace(self):
        plan = PLAN.replace("  - config/packages/framework.yaml:14\n```", "  - findings/privacy.md (Q-SEC-01)\n```")
        self.assertFlags("ERROR", "points into the workspace", plan=plan)

    def test_plan_location_repository_dirs_pass(self):
        plan = PLAN.replace("  - config/packages/framework.yaml:14\n```",
                            "  - config/packages/framework.yaml:14\n  - tickets/models.py:12\n  - reports/views.py\n```")
        code, out = self.run_on(self.workspace(plan=plan))
        self.assertNotIn("points into the workspace", out)

    def test_plan_location_dot_slash(self):
        plan = PLAN.replace("  - config/packages/framework.yaml:14\n```", "  - ./findings/app-security.md\n```")
        self.assertFlags("ERROR", "points into the workspace", plan=plan)

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

    FIXED = (FINDING.replace("resolution: open", "resolution: fixed").replace("on: 2026-10-10", "on: 2026-10-20")
             .replace("Reproduced.\n", "Reproduced.\nFix checked 2026-10-20 at 9f8e7d6: fixed by 1234abc (PR #7).\n"))
    DONE = (PLAN.replace("findings: [F-SEC-001]", "findings: []").replace("status: open", "status: done")
            .replace("| 1 | R-001 | Secure the session cookie | medium | S | code | — | yes |\n", "")
            .replace("generated: 2026-10-12", "generated: 2026-10-21"))

    def test_fixed_finding_and_done_fix(self):
        code, out = self.run_on(self.workspace(finding=self.stamped(self.FIXED), plan=self.DONE),
                                "--require", "verification", "--require", "plan")
        self.assertEqual(code, 0, out)
        self.assertIn("errors 0, warnings 0, pending 0", out)

    def test_fixed_without_fix_check(self):
        self.assertFlags("ERROR", "resolution fixed without a `Fix checked",
                         finding=FINDING.replace("resolution: open", "resolution: fixed"), plan=self.DONE)

    def test_fix_check_in_part_keeps_open(self):
        finding = self.FIXED.replace("fixed by 1234abc (PR #7)", "in part: the flag; remains the header")
        self.assertFlags("ERROR", "resolution fixed, its last fix check (2026-10-20 at 9f8e7d6) says in part",
                         finding=finding, plan=self.DONE)
        code, out = self.run_on(self.workspace(finding=finding.replace("resolution: fixed", "resolution: open")))
        self.assertEqual(code, 0, out)

    def test_fix_check_moves_on(self):
        self.assertFlags("ERROR", "fix checked 2026-10-20, verification `on` still 2026-10-10",
                         finding=self.FIXED.replace("on: 2026-10-20", "on: 2026-10-10"), plan=self.DONE)

    def test_fix_check_makes_plan_stale(self):
        self.assertFlags("PENDING remediation-plan", "no longer confirmed and open", finding=self.FIXED)

    def test_done_fix_in_order(self):
        plan = self.DONE.replace("|---|---|---|---|---|---|---|---|\n",
                                 "|---|---|---|---|---|---|---|---|\n| 1 | R-001 | Secure the session cookie | medium | S | code | — | no |\n")
        self.assertFlags("ERROR", "R-001: done fix listed in `## Order`", finding=self.FIXED, plan=plan)

    def test_done_fix_with_open_finding(self):
        plan = PLAN.replace("status: open", "status: done")
        self.assertFlags("ERROR", "R-001: done, but F-SEC-001 is not fixed", plan=plan)

    def test_lead_from_verify_waits_for_pass(self):
        ff = FINDINGS_FILE.replace("open: owner,\n  Q-SEC-01.", "open: from verify-findings 2026-10-20;\n  agent.")
        self.assertFlags("PENDING lead-pass", "L-SEC-02: opened by verify-findings", findings_file=ff)

    def test_lead_closed_as_remains_of_unknown_finding(self):
        ff = FINDINGS_FILE.replace("open: owner,\n  Q-SEC-01.", "closed: remains of F-SEC-009's fix\n  (Fix checked 2026-10-20).")
        self.assertFlags("ERROR", "F-SEC-009", findings_file=ff)

    def test_no_plan_with_confirmed_findings(self):
        self.assertFlags("ERROR", "no plan yet", plan=None, args=("--require", "plan"))

    def test_fingerprint_ignores_status_note_and_wrapping(self):
        base = self.sha()
        self.assertEqual(base, self.sha(FINDING.replace("status: confirmed", "status: refuted")))
        self.assertEqual(base, self.sha(FINDING.replace("Reproduced.", "Reproduced.\nRe-checked 2026-10-12, answer of 2026-10-11: no change.")))
        self.assertEqual(base, self.sha(FINDING + "\nA paragraph of the note.\n"))
        self.assertEqual(base, self.sha(FINDING.replace("Cause, consequence.", "Cause,\nconsequence.")))
        self.assertEqual(base, self.sha(FINDING.replace("on: 2026-10-10", "on: 2026-10-11")))

    def test_fingerprint_sees_text_rating_and_answers(self):
        base = self.sha()
        self.assertNotEqual(base, self.sha(FINDING.replace("Set it to auto", "Set it to on")))
        self.assertNotEqual(base, self.sha(FINDING.replace("severity: medium", "severity: high")))
        self.assertNotEqual(base, self.sha(FINDING + "\n**Auditor answer.** Q-SEC-01, answer 2026-10-11: kept.\n"))
        self.assertNotEqual(base, self.sha(FINDING + "\n**Changed by lead pass.** 2026-10-11: new evidence.\n"))

    def test_same_day_change_is_pending_then_required(self):
        changed = self.stamped().replace("Set it to auto", "Set it to on")
        code, _ = self.assertFlags("PENDING verify-findings", "text changed since its verification", finding=changed)
        self.assertEqual(code, 0)
        code, _ = self.assertFlags("ERROR", "text changed since its verification", finding=changed,
                                   args=("--require", "verification"))
        self.assertEqual(code, 1)

    def test_same_day_answer_is_pending(self):
        finding = self.stamped() + "\n**Auditor answer.** Q-SEC-01, answer 2026-10-10: severity high.\n"
        self.assertFlags("PENDING verify-findings", "text changed since its verification", finding=finding)

    def test_sha_form(self):
        self.assertFlags("ERROR", "not a 12-character hash",
                         finding=FINDING.replace("on: 2026-10-10}", "on: 2026-10-10, sha: abc}"))

    def test_without_sha_is_one_warning(self):
        code, out = self.run_on(self.workspace())
        self.assertEqual(code, 0, out)
        self.assertIn("1 verified findings without `sha`", out)
        self.assertNotIn("text changed since", out)

    def test_plan_sees_a_same_day_change(self):
        finding = self.stamped()
        plan = self.sourced(finding)
        changed = self.stamped(FINDING.replace("Set it to auto", "Set it to on"))
        self.assertFlags("PENDING remediation-plan", "F-SEC-001 changed since the plan", finding=changed, plan=plan)
        code, out = self.run_on(self.workspace(finding=finding, plan=plan), "--require", "plan")
        self.assertEqual(code, 0, out)

    def test_plan_without_sources_is_one_warning(self):
        code, out = self.run_on(self.workspace())
        self.assertIn("1 open fixes without `sources`", out)

    def test_recheck_without_change_keeps_plan_sources(self):
        finding = self.stamped()
        plan = self.sourced(finding)
        code, out = self.run_on(self.workspace(
            finding=finding.replace("Reproduced.", "Reproduced.\nRe-checked 2026-10-11, lead pass of 2026-10-11: no change."), plan=plan))
        self.assertNotIn("changed since", out)

    PASS = "skill: app-security@0.26.0 (2026-10-11), tools: [semgrep@1.0]"

    def test_same_day_answer_waits_for_lead_pass(self):
        ff = FINDINGS_FILE.replace("skill: app-security@0.20.0, tools: [semgrep@1.0]", self.PASS)
        self.assertFlags("PENDING lead-pass", "Q-SEC-01: answered 2026-10-11", findings_file=ff)

    def test_same_day_answer_under_older_skills_says_nothing(self):
        ff = FINDINGS_FILE.replace("skill: app-security@0.20.0, tools: [semgrep@1.0]", self.PASS.replace("0.26.0", "0.20.0"))
        code, out = self.run_on(self.workspace(findings_file=ff))
        self.assertNotIn("Q-SEC-01: answered", out)

    def test_applied_answer_does_not_wait(self):
        ff = (FINDINGS_FILE.replace("skill: app-security@0.20.0, tools: [semgrep@1.0]", self.PASS)
              .replace("accepts the proposal: 5 MB.", "accepts the proposal: 5 MB.\n  **Applied (2026-10-11).**"))
        code, out = self.run_on(self.workspace(findings_file=ff))
        self.assertNotIn("Q-SEC-01: answered", out)
        self.assertEqual(code, 0, out)

    def test_applied_form(self):
        ff = FINDINGS_FILE.replace("accepts the proposal: 5 MB.", "accepts the proposal: 5 MB.\n  **Applied 2026-10-11.**")
        self.assertFlags("ERROR", "not `**Applied (YYYY-MM-DD).**`", findings_file=ff)

    def test_earlier_answer_needs_no_mark(self):
        ff = FINDINGS_FILE.replace("skill: app-security@0.20.0, tools: [semgrep@1.0]", self.PASS.replace("10-11", "10-12"))
        code, out = self.run_on(self.workspace(findings_file=ff))
        self.assertNotIn("Q-SEC-01: answered", out)

    def test_priority_comes_first_in_its_tier(self):
        finding2 = FINDING.replace("F-SEC-001", "F-SEC-002").replace("severity: medium", "severity: low").replace("Settles L-SEC-01.", "")
        low = (PLAN[PLAN.index("### R-001"):PLAN.index("## Discrepancies")]
               .replace("R-001", "R-002").replace("F-SEC-001", "F-SEC-002").replace("severity: medium", "severity: low"))
        plan = (PLAN.replace("## Discrepancies", low + "## Discrepancies")
                .replace("| 1 | R-001 | Secure the session cookie | medium | S | code | — | yes |\n",
                         "| 1 | R-002 | Secure the session cookie | low | S | code | — | no |\n"
                         "| 2 | R-001 | Secure the session cookie | medium | S | code | — | yes |\n"))
        self.assertFlags("WARNING", "not by priority, severity, then effort", finding=FINDING + "\n" + finding2, plan=plan)
        kept = plan.replace("id: R-002", "id: R-002\npriority: before launch, the owner's decision (Q-SEC-01)")
        code, out = self.run_on(self.workspace(finding=FINDING + "\n" + finding2, plan=kept))
        self.assertNotIn("not by priority", out)

    def engagement(self, **fields):
        return {"00-engagement.md": ENGAGEMENT + "".join("%s: %s\n" % kv for kv in fields.items())}

    def test_execution_value(self):
        self.assertFlags("ERROR", "execution `sometimes`", extra=self.engagement(owner="auditor", execution="sometimes"))

    def test_execution_on_third_party(self):
        self.assertFlags("ERROR", "only `none` is allowed", extra=self.engagement(owner="third party: Acme", execution="disposable-copy"))

    def test_local_target_needs_active(self):
        self.assertFlags("ERROR", "needs `testing: active`", extra=self.engagement(owner="auditor", testing="passive", execution="local-target"))

    def test_execution_allowed(self):
        code, out = self.run_on(self.workspace(extra=self.engagement(owner="auditor", testing="active", execution="local-target")))
        self.assertEqual(code, 0, out)
        code, out = self.run_on(self.workspace(extra=self.engagement(owner="third party: Acme", testing="passive", execution="none")))
        self.assertEqual(code, 0, out)

    def test_unreadable_workspace(self):
        code, _ = self.run_on(tempfile.mkdtemp())
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
