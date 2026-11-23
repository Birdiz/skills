# performance

## Coverage

skill: performance@0.26.0 (2026-10-11), tools: [lighthouse@12]

## Findings

### F-PERF-001 Large hero image

```yaml
id: F-PERF-001
axis: performance
status: confirmed
verification: {by: sub-agent, on: 2026-10-12}
severity: medium
confidence: high
evidence_regime: dynamic
effort: S
resolution: open
sensitive: false
promptable: true
locations:
  - https://acme.example/
commit: a1b2c3d
references: []
```

**Evidence.** 4 MB image, see `tool-output/lighthouse.json:12`.

**Technical explanation.** LCP 6 s.

**Plain-language explanation.** The page shows late.

**Remediation.** Compress it.

**Verification.** by: sub-agent, 2026-10-12. Seen.

## Leads

None.
