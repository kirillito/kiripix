---
status: todo
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0300-m5-clip-attach.md, 0301-m5-held-thing-import.md]
---

# M5: `render` draws a clip's held things at their socket

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- In `blender/render_frames.py`: each thing parented to its socket bone with its `offset` and `turn`, shown only in the clips that
  attach it, its materials in the material pass after the Model's, and included in the measure pass (so the clip's extent holds it).
- `render.json` records each clip's `attach`. `render` Stage `version` bump.
- **Points:** a thing's socket is a point (`render points=hand_r@grip_r` was the trial's fix, 0238 step 5: `hand_r` at the wrist is 2-3 px
  from the grip). Default `points` to include the sockets a clip attaches at, so the game's fallback and the real thing agree.
- The phone vanishes behind the body in many frames (the pose); that's the true depth, and the point's `hidden` flag says so.
- Run on the real Blender in the tests ([0281](0281-m5-real-blender-tests.md)'s seam).

## Acceptance criteria

- [ ] Real-Blender test: a fixture character with a socket bone and a thing in one clip: the thing's pixels appear only in that clip, in
      every direction, within a pixel of the socket's point.
- [ ] A Model without the socket bone gives `clips.unknown_socket` before rendering.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
