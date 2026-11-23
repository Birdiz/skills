# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root: this repo's glossary, the shared vocabulary for the skills, findings and reports.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.

This repo is single-context: there is no `GLOSSARY-MAP.md` and no per-context glossary.

When a term gets resolved, add it to `GLOSSARY.md`. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) records new ADRs in `docs/adr/` when decisions actually get resolved.

## File structure

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-files-as-contract.md
│   ├── 0002-two-level-setup.md
│   ├── 0003-invariants-are-not-configurable.md
│   ├── 0004-execution-is-a-recorded-choice.md
│   └── 0005-two-plugins-share-a-copied-core.md
├── core/                  # the finding core, edited here only
├── plugins/
│   └── birdiz-audit/      # one plugin: manifest, skills, changelog, copy of core/
└── tools/                 # sync_core.py and the repository's own tests
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0003 (invariants are not configurable), but worth reopening because…_
