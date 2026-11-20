---
status: todo
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0341-m6-room-normals-stage.md]
---

# M6: UI: the room's normals screen, lit by a light the Owner moves

Spec §11 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Over
[0341](0341-m6-room-normals-stage.md)'s Stage; no logic in the UI beyond drawing.

## What to build

- **The normals screen:** the `mode` switch (off or depth) and the Stage's parameters from `describe`. Below them, the room
  lit by a point light that follows the mouse (a 2D dot-product shading on the canvas, a preview only, not Godot's),
  with a toggle to the raw normal image.
- **The fix:** a `flatten` brush and polygon (as the masks screen's tools), and the Override brush. Each stroke is one
  `decide` or `override` on release.
- `normals.not_flat_walkable` findings jump to their area, as other findings do.

## Acceptance criteria

- [ ] Playwright against a real `kiripix serve` with the stub Runner: switching `mode` to depth builds the Stage, a `flatten`
      stroke records one Decision, and the finding clears.
- [ ] `npm run build` passes.
- [ ] An eye check by the Owner on a ch01 dungeon room, noted here.
