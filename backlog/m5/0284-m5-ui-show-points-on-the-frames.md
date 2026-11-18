---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0237-m5-render-records-named-points.md]
---

# M5: UI: show a character's named points on its frames

Spec §11. After [0237](0237-m5-render-records-named-points.md): `render` records named points (`hand_r`, `head`, a socket) per
frame, and the game draws the phone, VFX and bubbles at them. The Owner needs to see that a point sits where the game will
draw.

## What to build

- On the character's frame views (render, finish and sheet screens), a toggle draws each named point as a 1-px cross in a
  contrasting colour, with its name on hover. A `hidden` point (behind the body) is drawn hollow.
- On the clips screen's playback, the points follow the frames, so a phone's path can be watched at the game's speed.
- The data comes from the Stage's output through the file route (`render.json`) or `show`, as the frame views already read it.

## Acceptance criteria

- [x] Playwright, on a fake-Blender character with a `hand_r` point: the toggle draws one cross per frame at the recorded
      pixel, and a hidden point is hollow.
- [x] `npm run build` passes.

## Result

The frame screen (`render`, `palette`, `finish`, `sheet`) reads each frame's `points` from `render.json` (sub-pixel, drawn at
the pixel that holds it) or `sheet.json` (the cell's pivot plus the whole-pixel offset). A "Points" toggle (key `H`, on by default,
shown only when a frame has points) draws a 1-px cross per point on the big view and on every thumbnail; the name is the hover
title. A `hidden` point is a hollow square. The big view follows the frames as the Clip is stepped or played, which is the
playback the ticket wants (the clips screen is a parameter table with no player, so the Player of the frame screen is the one).
Nothing is sent to the server; no Command was missing.

Tests: `web/e2e/points.spec.ts` (render: one cross per thumbnail at the recorded pixel, follows the frame, hollow in `n`, toggle;
sheet: pivot plus offset). `npm run build` passes. Screenshot: `web/shots/0284-points.png`.

Review fixes: neither `show` nor `render.json`/`sheet.json` gives the pixel in the picture shown (render has sub-pixel places,
sheet has offsets from the pivot), so the `floor` and pivot-plus-offset stay as display-only math in one helper, `pointsOf` in
`web/src/frameScreen.tsx`; no backend change. The cross is now made of image pixels (the pixel and one each way), so it scales
with the zoom and marks the exact pixel; a hidden point is still hollow.

The Owner, 2026-11-17: "the clips screen's playback" is the frame screen's Player, which plays a Clip; the clips screen has
no player of its own. Accepted as built.
