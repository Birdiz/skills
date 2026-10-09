# code-quality areas and severity

## Areas

- **Correctness**: defects on the main flows: unhandled cases, wrong conditions, partial writes, races, time zones, money as floats.
- **Error handling**: errors swallowed, logged and ignored, turned into success; generic catches; failures leaving inconsistent state.
- **Complexity**: hotspots (size and branching of frequently changed code), deep nesting, functions doing several jobs.
- **Duplication**: copied logic, and whether the copies have already diverged.
- **Dead and unfinished code**: unreachable code, feature flags never removed, `TODO` on main flows; absence of a caller is not proof.
- **Types and contracts**: type checking on or off, `any` and suppressions on main flows, unhandled nulls, invariants not enforced.
- **Tests**: what the main flows' tests assert and mock away, flows without tests, tests that cannot fail.
- **Consistency**: the project's own conventions, and where the code departs from them.
- **Dependencies**: outdated or abandoned packages, several libraries for one job, declared but unused; known vulnerabilities belong to `app-security`.
- **Delivery checks**: what CI runs (lint, types, tests) and whether a failure blocks a merge.

## Severity grid

What the problem does, and where it shows. "Main flow" is the flow of the
codebase map where the wrong result reaches a user, wherever its cause
lies.

| | Main flow | Other production code | Non-production code (tests, scripts, tooling) |
|---|---|---|---|
| Defect shown: data loss or corruption, a side effect silently not done | critical | high | low |
| Defect shown: wrong result or crash, no data lost | high | medium | low |
| Condition that makes a defect likely, not shown to fire | medium | low | info |
| Change shown slower or riskier (hotspot, diverged copies, no test) | medium | low | info |
| Hygiene, no shown consequence | low | info | info |

The grid assumes a precondition met in ordinary use. A rare one (a narrow
window, an unusual sequence of administrative actions) lowers one level; a change the problem blocks, planned by the owner (in an
answer or in the repository's own plans), raises one. Any
move states its reason with a pointer.
