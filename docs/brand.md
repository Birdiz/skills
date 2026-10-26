# Visual identity

<img alt="The mark: a lens over three lines, the middle one in orange" src="assets/mark.svg" width="64">

The mark is a lens over three lines of findings, one of them singled out.
The images in the README follow the rules below; edit
[generate.py](assets/generate.py), not the SVG files, then run
`python3 docs/assets/generate.py` (Python 3, standard library only).

## Colors

| Token | Light | Dark | Use |
|---|---|---|---|
| ink | `#1B1F3B` | `#E7E9F3` | text, the lens, skills you run |
| muted | `#5D6480` | `#9AA1BC` | secondary text, wires |
| line | `#CDD2E1` | `#3A4160` | card borders |
| accent | `#E8772E` | `#F28C3C` | what the eye should land on: axes, the lead-pass loop, one line in the lens |
| ok / bad / idle | `#2E9E6B` / `#D64545` / `#8A90A6` | `#3DBA82` / `#EF6B6B` / `#8A90A6` | confirmed, refuted, unverified, and nothing else |

One accent only. Severity colors are not part of the identity: a report
uses the auditor profile's scale.

## Type

- Skill and file names in monospace (`ui-monospace`, Menlo, Consolas).
- Everything else in the system sans-serif stack.

## Shapes

- A skill you run (`/audit-setup`, `/audit-kickoff`) is a filled card; a
  skill the agent runs is an outlined card.
- Axes are orange pills.
- A dashed orange line is a loop that only touches what it concerns.
- Backgrounds stay transparent. Each image exists in a light and a dark
  file, picked in the README with `<picture>` so it follows the reader's
  GitHub theme.
