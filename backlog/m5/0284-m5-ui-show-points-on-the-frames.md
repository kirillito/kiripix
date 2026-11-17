---
status: todo
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

- [ ] Playwright, on a fake-Blender character with a `hand_r` point: the toggle draws one cross per frame at the recorded
      pixel, and a hidden point is hollow.
- [ ] `npm run build` passes.
