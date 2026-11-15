---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0189-m4-loops-stage.md, 0190-m4-export-loops.md]
---

# M4: a Loop that rests on frame 0 and never plays it

Found by trial [0184](0184-m4-ambient-animation-trial.md) (2026-11-14). Spec §6.1 (`loops`), §9 (`room.json`).

A Loop's frame 0 is the room, so a paused room, a capture at frame 0 and the Plate test are unchanged. The kitchen's TV is
off in the room, and its news Loop shows it on. A `timing` must give every frame at least 1 tick, so the TV goes dark for at
least a tick on every loop. The same holds for any screen, sign or lamp that is always on while the painting shows it off.

## What to build

- **`timing.rest`** (boolean, default false): frame 0 is the rest frame. The `sequence` leaves it out, so it plays frames
  1 to N-1 only. Frame 0 is still the room, and the game still shows it when it holds every Loop at frame 0 (its dev hook
  for the Plate test and captures).
- With `rest`, `ticks` as a list gives N-1 numbers (frames 1 on), `pingpong` runs 1 … N-1 … 2, and `flicker` draws from
  frames 1 to N-1. A Loop with `rest` and fewer than 3 frames is refused (`rest` needs at least two frames to play).
- `loop.seam`, `loop.still` and `loop.flash` measure the played sequence. `loop.frame0` is unchanged.
- **Export:** `room.json`'s `loops[].sequence` has no frame 0, and the Loop gains `rest: true`. The Godot node keeps
  `frame = 0` in the scene. The game sets it to the first played frame on its first tick (a line for its backlog, not
  Kiripix work). `room.json`'s `schema_version` moves on, with the refusal of the old format that the Stage's rule allows
  through M3.
- `describe` for `loops` names `rest`; the loops screen shows a Rest checkbox under Timing (one line in `loopScreen.tsx`,
  or a follow-up for the UI if it doesn't fit here).

## Acceptance criteria

- [x] CLI seam: a 4-frame Loop with `rest` has a sequence over frames 1 to 3 only; its frame 0 is still the room.
- [x] CLI seam: `rest` on a 2-frame Loop is refused.
- [x] CLI seam: the exported `room.json` has `rest: true` and no frame 0 in `sequence`.

Budget: 60–120k tokens.

## Result (2026-11-14)

- `timing.rest` (boolean, default false) in `sequence_of` (`kiripix/recipes/loops.py`): the played frames are 1 to N-1. `ticks` as
  a list gives N-1 numbers, `pingpong` runs 1 ... N-1 ... 2, `flicker` draws from frames 1 to N-1. `loop.seam`, `loop.still` and
  `loop.flash` measure the played sequence (a rotating cycle with `rest` takes the seam of the sequence, not the cycle's own);
  `loop.frame0` is unchanged. `rest` survives `_slowed`, so a flash fix keeps it.
- Held: `rest` with fewer than 3 frames ("`rest` needs at least 3 frames ...") and a `ticks` list of the wrong length under `rest`,
  both through the existing timing-length reasons (`_held_frames`, `_held_cycle`), whose owner action still says "one number per
  frame" (not reworded for `rest`).
- `ROOM_SCHEMA_VERSION` is 10: each `loops` entry gains `rest`; `sequence` has no frame 0 under it. Schema counts 10 in
  `test_export.py`, `test_export_layers.py` (edited, not run here). The scene is unchanged (`frame = 0`).
- `describe` for the `timing` Decision names `rest`. `web/src/loopScreen.tsx`: a Rest checkbox (`loop-rest`) under Timing;
  `setTiming` carries `rest` along, because a timing Decision replaces the whole one before it. Toggling it on while `ticks` is
  a per-frame list of N holds the Loop until the list is N-1 long. `npm run build` passes; Playwright not run.
- Tests: `test_loops.py` (2: played sequence over pingpong, list ticks and flicker; held reasons), `test_export_loops.py` (1).
- Left for the game's backlog: set `frame` to the first played frame on its first tick.
