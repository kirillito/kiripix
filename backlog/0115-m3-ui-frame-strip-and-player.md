---
status: done
milestone: M3
agent: ui-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0112-m3-sheet-stage.md, 0114-m3-ui-model-rig-clips-screens.md]
---

# M3: the frame strip, onion skin, direction picker and clip player

Spec §11 (Character: "a frame strip with onion skin, a direction picker and a clip player at game speed"). Story 15 of
[0097](0097-m3-characters.md).

## What to build

- On `render`, `palette`, `finish` and `sheet`: a frame strip for the chosen clip and direction, at integer zoom with
  nearest-neighbour rendering, read from the Stage's outputs (`sheet.json` on `sheet`).
- Onion skin: the previous and next frames faintly under the current one, toggled by a key.
- A direction picker laid out as a compass, with the number pad's keys.
- A clip player at the clip's frame rate, looping when the clip loops, with play, pause and step.
- A normal-map view: the normal frames, or the colour frame lit by a light that follows the mouse, if it needs no logic
  beyond drawing.
- Findings with a frame (pivot drift, an empty frame) jump to that clip, direction and frame.

## Acceptance criteria

- [x] Playwright, on the fake renderer: step through a clip, switch direction by key, play at the clip's speed, and click a
      `sheet.pivot_drift` finding to land on its frame.
- [x] No canvas smoothing anywhere; zoom stays integer.
