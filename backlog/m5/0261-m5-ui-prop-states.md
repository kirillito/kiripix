---
status: todo
milestone: M5
agent: ui-engineer
type: ticket
parent: 0257-m5-prop-states.md
depends_on: [0259-m5-prop-stages-per-state.md]
---

# M5: UI: a Prop's states

Spec §11. Part of [0257](0257-m5-prop-states.md). Built on the Commands of [0258](0258-m5-prop-state-decision-and-import.md)
and [0259](0259-m5-prop-stages-per-state.md), with no logic of the UI's own.

## What to build

- **A state strip** on the Prop's screens: the default and each state as a thumbnail, with its pick, status and findings.
  Declare, import and pick a state from it.
- The `cutout`, `fit` and `footprint` screens work on the selected state, and every Decision they record names it.
- **Side by side:** the states at 1x on one ground line, each at its origin, so the Owner sees that they match in scale.

## Acceptance criteria

- [ ] Playwright: on a fixture Prop with two states, selecting the second and drawing a footprint records a Decision naming
      it, and the side-by-side view shows both at their origins.
- [ ] `npm run build` passes.
