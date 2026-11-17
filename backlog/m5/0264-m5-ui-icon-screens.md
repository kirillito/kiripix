---
status: todo
milestone: M5
agent: ui-engineer
type: ticket
parent: 0253-m5-icon-kind.md
depends_on: [0262-m5-icon-kind-and-stages.md]
---

# M5: UI: the icon's screens

Spec §11. Part of [0253](0253-m5-icon-kind.md).

## What to build

- The icon's Stages reuse the Prop's screens (`source`, `cutout`, `fit`, `palette`, `finish`), with the square drawn on `fit`.
- The status board lists icons under their Kind, as it does every Asset.

## Acceptance criteria

- [ ] Playwright: a fixture icon opens on the reused screens, with the square drawn on `fit`.
- [ ] `npm run build` passes.
