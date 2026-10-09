# accessibility areas and severity

## Areas

- **Keyboard**: every control reachable and operable, focus order, no trap, bypass of repeated blocks, shortcuts that can be turned off.
- **Focus**: always visible, never hidden behind other content, moved sensibly after dialogs and partial reloads.
- **Names, roles, states**: controls, links and images named for what they do or mean; roles and states exposed; custom widgets built on the right pattern.
- **Forms**: labels, instructions, required fields, error identification and suggestion, input kept, autocomplete purposes on personal fields.
- **Structure**: page title, language, headings, landmarks, lists and tables marked up as such.
- **Dynamic content**: status messages and partial reloads announced, no unexpected change of context.
- **Contrast and colour**: text and non-text contrast, information not conveyed by colour alone.
- **Zoom and reflow**: 200% zoom, reflow at 320 CSS pixels, text spacing, orientation.
- **Media and motion**: text alternatives for meaningful images, captions and transcripts, animations that can be paused, nothing flashing.
- **Timing and authentication**: time limits that can be extended, sign-in without a cognitive test or with an alternative.

## Severity grid

What it does to a person who relies on the feature, and where. "Main flow"
is a flow of the codebase map.

| | Main flow | Other pages | One page or element |
|---|---|---|---|
| Blocks a task for some users (keyboard trap, control unreachable or unnamed, error never announced) | high | medium | low |
| Task possible only with real difficulty or a workaround (focus invisible, low contrast on body text, broken reflow) | medium | medium | low |
| Degrades the experience without blocking (heading order, missing landmark, redundant link text) | low | low | info |
| Non-conformance with no effect shown on a user | info | info | info |

One level up when the owner states they are bound by an accessibility
obligation: the gap is then legal exposure too. Other moves of one level:
`finding-format`, Rating.
