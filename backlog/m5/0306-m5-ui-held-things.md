---
status: todo
milestone: M5
agent: ui-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0302-m5-render-attached-things.md]
---

# M5: UI: a clip's held things, and their socket on the frames

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- On the clips screen, a clip's `attach` (thing, socket, offset, turn) edited as a Decision; the Asset's things listed with their imports.
- On the frames, the socket's point drawn (with [0284](0284-m5-ui-show-points-on-the-frames.md)'s points), so the Owner checks that each thing
  sits in the hand.

## Acceptance criteria

- [ ] Playwright: on a built fixture with a thing, attaching it to a clip records the Decision, and the socket's point shows on the frames.
- [ ] `npm run build` passes.
