# architecture areas and severity

## Areas

- **Boundaries**: the real modules and what each hides; modules whose interface is nearly as large as their implementation; one concept's logic spread over many modules.
- **Dependency direction**: the layering the project states or implies, edges breaking it, cycles between modules.
- **Change coupling**: modules that change together in history, and what that says about the boundaries.
- **Data ownership**: which module writes each store or table; data written from several places; databases shared between deployables; duplicated sources of truth.
- **Consistency**: writes to several stores or services without a transaction, an outbox or a recovery path; retries that can duplicate side effects.
- **Failure between components**: timeouts, retries and fallbacks on calls to other services and third parties; what a slow or absent dependency does to the main flows.
- **Third-party coupling**: vendor SDKs and frameworks spread across the domain instead of behind one adapter, and what replacing them would touch.
- **Configuration and environments**: where configuration is read, code paths that differ by environment, settings duplicated across components.
- **Operability**: what a production failure leaves to diagnose it: structured logs, correlation across components, health checks, jobs and queues that can stall silently.
- **Documentation**: ADRs, diagrams and READMEs against the code; decisions taken and not recorded.

## Severity grid

What the structure causes, and how much of the system it reaches: "most
main flows" is more than half of the map's flows.

| | Most main flows | One module or flow | Local |
|---|---|---|---|
| Structural cause of data loss, inconsistency or outage | high | medium | low |
| Change shown slower or riskier (cycle, broken layer, coupling in history) | medium | medium | low |
| Gap that delays diagnosis or a decision (an unwatched component, a health check that misses the application, decisions the team cannot read) | low | low | info |
| Divergence from documented architecture, no shown cost | low | low | info |
| Observation | info | info | info |

`critical` only when the failure is shown to happen now, and the finding says
so. A failure nobody would notice (a stopped worker, a queue nobody watches)
is an outage of what it carries. Moves of one level: `finding-format`,
Rating.
