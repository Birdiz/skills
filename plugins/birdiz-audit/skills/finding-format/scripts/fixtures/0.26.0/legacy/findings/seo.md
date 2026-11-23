# seo

## Coverage

skill: seo@0.20.0, tools: []

| Area | Status |
|---|---|
| Titles | evaluated |

## Findings

### F-SEO-001 Duplicate titles

```yaml
id: F-SEO-001
axis: seo
status: confirmed
verification: {by: sub-agent, on: 2026-10-12, sha: 222222222222}
severity: low
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

**Evidence.** Every page is titled "Acme".

**Technical explanation.** Search engines merge them.

**Plain-language explanation.** Pages compete with each other.

**Remediation.** One title per page.

**Verification.** by: sub-agent, 2026-10-12. Seen.

### F-SEO-002 No sitemap

```yaml
id: F-SEO-002
axis: seo
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
  - https://acme.example/sitemap.xml
commit: a1b2c3d
references: []
```

**Evidence.** 404.

**Technical explanation.** Crawlers guess.

**Plain-language explanation.** Pages are found late.

**Remediation.** Publish one.

**Verification.** by: sub-agent, 2026-10-12. Seen.

## Leads

None.
