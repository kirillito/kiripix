---
status: done
milestone: M6
agent: godot-export
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0362-m6-sprite-effect-parameters.md, 0364-m6-export-effect-blend.md]
---

# M6: a clip's `ticks` reach `frames.tres`

Spec §9 and §6.4. Found after [0362](0362-m6-sprite-effect-parameters.md) and [0364](0364-m6-export-effect-blend.md): a `clip`
Decision's `ticks` (one duration per frame, 60 a second) reach `character.json` as `clips[].ticks`, but the SpriteFrames still gave
every frame `"duration": 1.0` at the clip's `fps`, so a Pixelbolt render's timing was lost in the game unless it read
`character.json` itself.

## What to do

- In `frames.tres`, an animation whose clip has `ticks` plays at `speed` 60 and each frame's `duration` is its ticks (Godot shows a
  frame for duration / speed seconds). A clip without `ticks` is written exactly as before.

## Acceptance criteria

- [x] CLI seam: a sprite's `frames.tres` has durations 1.0 and its fps without `ticks`, and its ticks at speed 60 with them.
- [x] A sprite without `ticks` exports byte for byte as before.

## Result (2026-11-21, main session, a small one-file change)

`character_frames` in `kiripix/export/godot.py`: `TICKS_PER_SECOND = 60`; a clip with `ticks` gets `"speed": 60.0` and each frame
`"duration": <its ticks>.0`, by the frame's place in its direction's list. Without `ticks` nothing changes, so no exported file
changes for an existing sprite or character. No Stage changed (the writer is export's), so no `version` bump. Test:
`tests/cli/test_export_sprite.py::test_a_clip_with_ticks_plays_at_60_a_second_each_frame_its_own_ticks`.
