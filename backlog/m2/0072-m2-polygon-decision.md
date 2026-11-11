---
status: done
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: fill a polygon on a Mask in one Decision

Spec §6.1 (masks). Found by [0062](0062-m2-claude-first-pass-trial.md). Claude's first pass filled every wall, pit and object
with `brush` zigzags: 89 strokes across three rooms, 23 of them on r01 only to close the dotted seams a radius-1 stroke leaves.
The trial's only correction was a box over a bench that isn't rectangular, which a polygon would have fitted. The `masks`
description already names "polygon", and spec §6.1 says that it isn't built yet.

## What to build

- An Op in `kiripix/ops/masks.py` that fills a polygon on a Mask, or clears it with `erase`. It's pure and exact: the filled
  pixels are fixed for given points, the edge pixels are included, and a self-crossing polygon follows the even-odd rule. Points
  outside the Mask are clipped.
- A `polygon` Decision on `masks`: `{mask, erase, points}`, with at least three points in target pixels. It closes itself. It
  isn't `on_image`, like `brush` and `border`, so a changed Plate doesn't send it to `needs-review`.
- It replays in journal order with the other Decisions.
- `describe` then tells the truth, and spec §6.1 loses "A polygon tool isn't built yet". This ticket adds no UI;
  [0080](../m3/0080-m3-ui-polygon-tool.md) does that.

## Acceptance criteria

- [x] A rectangle by `polygon` is pixel-identical to the same box filled by hand, with no seam: golden test at the Op seam.
- [x] A concave polygon (an L, like r03's ticket booth) fills correctly, and `erase` clears it, at the Op seam.
- [x] CLI seam: `decide`, then `run`, gives the Mask. `undo` removes it. A changed Plate leaves a `polygon`-only `masks` `done`.
- [x] Fewer than three points is refused with a finding.
- [x] `room.harbor_front`'s and the three dungeon rooms' journals still replay unchanged: no existing Decision changes meaning.
      Checked on the three dungeon rooms. `harbor_front` is waived by the Owner as a throw-away test room; see the notes.

## Notes

- Journal replay, checked 2026-11-06 at `cf44df7`, by `run <room> masks --force` on copies, so the art repo is unchanged. The
  change to `kiripix/recipes/room.py` only adds: the `polygon` branch in `_masks`, its `DecisionSpec` and one import.
  - **`ch01_dungeon_r01`, `r02`, `r03`: unchanged.** Each ran to `done` with the same `input_hash`, and `solid.png`, `pit.png` and
    `floods.json` are byte-identical to the rooms' earlier builds. Their journals hold `brush`, `flood` and `border`, no clicks.
  - **`room.harbor_front`: not replayed.** `masks` stops at `needs-input`, "Runner not run yet" (exit 3), so nothing was rebuilt.
    This doesn't come from this ticket: `c425c0a`, the commit before the polygon change, reports the same. `7b68578` reports
    `done` and `48006d2` doesn't. That commit made a negative `click` its own Runner call, so harbor_front's negative clicks
    probably have no pinned result; that link isn't proven. The Owner waived this room, and no ticket follows: it's a throw-away
    test room that won't go into the game.
