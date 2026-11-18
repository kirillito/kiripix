---
status: todo
milestone: M5
agent: godot-export
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0303-m5-cell-per-clip.md]
---

# M5: export a character whose clips have their own cells

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- `frames.tres`: each animation's `AtlasTexture` regions at its clip's cell. The scene's offset puts the pivot pixel at the origin per
  animation (today one offset for the scene): either a per-animation offset the game applies on `animation_changed`, or every frame's
  `AtlasTexture.margin` padding it to one logical cell. Pick the one the game's loader needs less work for, and say which in spec §9.
- Spec §9's Character row updated; the game's loader change is the Owner's (name it in the Result).

## Acceptance criteria

- [ ] CLI seam: the exported `.tres` of a fixture with one larger clip has that clip's regions at its cell; real-Godot test (skipped without
      Godot) loads the scene and plays both clips with the feet on the same pixel.
