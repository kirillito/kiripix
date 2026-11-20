---
status: done
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

- [x] CLI seam: the exported `.tres` of a fixture with one larger clip has that clip's regions at its cell; real-Godot test (skipped without
      Godot) loads the scene and plays both clips with the feet on the same pixel.

## Result

- **Route: `AtlasTexture.margin`** (not a per-animation offset on `animation_changed`). Each frame is padded to one logical cell, the smallest that holds every
  clip's cell with the pivots on one pixel (`logical_cell` in `kiripix/export/godot.py`): `margin = Rect2(logical pivot - clip pivot, logical size - clip cell)`. The scene
  keeps one offset, the logical pivot, so the game's loader does nothing new: no signal handler, no per-clip table. 0309 reuses it (a trimmed frame's margin is the same
  `Rect2`, its region just smaller), and 0307 proved region plus margin pixel-exact in Godot 4.7.2 (plain, `flip_h`, under a `CanvasTexture`). A character whose clips share
  one cell gets no `margin` and the body's pivot: its `.tres` and scene are byte for byte as before. A clip whose cell is the logical one has no margin; the others do.
  `frames.tres` and the scene change; `character.json` is copied as 0303 left it (the game's collision and point maths use the body's `pivot`; see below).
- **Tests:** `tests/cli/test_export_cell_per_clip.py` (the fixture of `test_cell_per_clip`: regions at each clip's own cell and packed rect, margins as computed from
  `character.json`, the scene's offset, no margin for one cell; a `godot`-marked test that draws the first frame of every clip in Godot 4.7.2 and finds the feet on the same
  row and each clip's cell at its own pivot); goldens `frames_wide.tres` and `hero_wide.tscn` in `tests/golden/test_character_export_writers.py`. The Godot test needs a
  renderer, so it runs Godot with OpenGL in a small window, not headless. It runs with `KIRIPIX_GODOT` set to the 4.7.2 console exe.
- **Spec §9:** the Character row gains the cell per clip, the logical cell and the margin.
- **The game's loader (the Owner):** nothing to change for drawing, foot events or points: the pivot pixel is at the scene's root in every animation, and points and
  foot frames are relative to it. Only a loader that reads a frame's size, or `cell` and `pivot` from `character.json`, for something else (a hitbox from the cell, say)
  sees that a frame texture is now the logical cell (the largest clip's) and the top-level `cell` and `pivot` stay the body's; each clip's own are in its `clips` entry.
- **Left:** the Wearable's `frames.tres` goes through the same writer, but its render still draws every clip at the body's cell (0303's note), so a Wearable over a body
  with a larger clip doesn't line up until that follow-up.
