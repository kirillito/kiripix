---
status: done
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

- [x] Playwright against a real `kiripix serve` with the stub Runner: switching `mode` to depth builds the Stage, a `flatten`
      stroke records one Decision, and the finding clears.
- [x] `npm run build` passes.
- [x] An eye check by the Owner on a ch01 dungeon room, noted here.

## Result

Built by the UI engineer; the last box (the Owner's eye on a ch01 dungeon room) is open, so the ticket stays `todo`.

**Files.** `web/src/normalsScreen.tsx` (the panel), `web/src/normalsTool.ts` (the lit canvas layer, the Override's PNG),
`web/src/App.tsx` (wiring: `isNormals`, the rebuild switch, `overrideNormals`), `web/e2e/normals.spec.ts` (3 flows). No change in `kiripix/`.

**The screen.** The Stage's parameters (`mode`, `size`, `strength`, `deadzone`, `levels`) come from `describe` through the shell's
generic controls, so `mode` is the off/depth switch; the panel adds the canvas parts. With `mode` off it says so and its tools are
disabled. Built, the canvas shows the room lit by a point light that follows the mouse (a 2D dot product over `normal.png` and the
room's palette image, ambient 0.35, a flat pixel keeps its colour; a preview, not Godot's), `L` or the View buttons switch to the raw
normal image. The boxes of `normals.not_flat_walkable` findings are drawn dashed, and a click on the finding jumps to it (the shell's
`jump`). The light is a hover and records nothing.

**The fix.** `F` Flatten: Brush `B`, Polygon `G`, and their unflatten twins `E` and `X` (`erase`), with a "Walkable pixels only"
checkbox (`walkable`); each is one `decide normals flatten` on release (a polygon on Enter or on a click of its first point), `[ ]`
change the brush size. "Rebuild the normals after each edit" (on by default) runs the Stage again after it: a flatten replays with no
Runner call. `Ctrl+Z` and `Ctrl+Shift+Z` are `undo` and `redo`.

**The Override brush has a backend, and the UI paints it.** `override` is a REST Command on any Stage with an image, and `normals`
has `image=normal.png`, so `O` Override works: Brush or Polygon with a picked normal (flat, or a 45 degree tilt up, down, left or
right, in Godot's encoding), drawn into a PNG of the room's size (the painted pixels opaque, the rest clear) and sent as one `override`
on release. The Stage has no Override tool of its own and `override` replaces whole pixels, so there is no finer control than
these presets; a hand-painted image is imported by the CLI (`kiripix override`). The normal presets and their encoding live in the UI
(`normalsScreen.tsx`): if the Owner wants them to be the Stage's, that is a backend ticket.

**Tests.** `npm run build` clean; `npx playwright test e2e/normals.spec.ts`: 3 passed (the acceptance flow with the fake depth
Runner: `mode` to depth, re-run, accept, a flatten stroke is one Decision and the finding clears, undo brings it back; the light follows
the mouse and the view switches; a walkable polygon and an Override are one Decision each). Not run: the other specs, the Python suite.

**Owner's eye check (open).** `kiripix ui`, open a ch01 dungeon room, set `mode` to depth on `normals`, re-run, accept, then move the
mouse over the lit room: walls should shade toward the light and floors stay near their colour. Flatten a floor patch the finding
boxes name (Polygon, "Walkable pixels only") and the finding should clear. Reference capture from the test room:
`web/test-results/normals-lit.png` (the ramp depth tilts the floor, so it shows boxes; the flattened one is
`web/test-results/normals-flattened.png`).

**The Owner's eye check, 2026-11-20:** looks fine; the difference is hard to tell exactly.
