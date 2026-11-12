---
status: todo
milestone: M4
agent: character-pipeline
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0156-m4-edit-a-clip.md, 0151-m4-export-part-ramps.md]
---

# M4: foot contact frames in `character.json`

Spec §6.3 (clips) and §9 (Character). Added 2026-11-12 for the game's M03-06 (footstep sounds on contact frames). Lower priority:
the last wave of M4, and the first to move to M5 if M4 is full. Without it, the game marks the frames by hand.

## The gap

The game plays a footstep when a foot plants. Without data from Kiripix it marks those frames by hand, per clip, for 4 bodies.
Kiripix has the foot bones in Blender.

The animation is the same in every direction (a direction is the camera's view of one action), so a plant is on the same frames in
all 8 directions: one list per clip, not per direction. That's per clip x 4 bodies, not x 8 more.

## What to build

- The `clips` Stage asks Blender, in the call it already makes per file (`read_actions`), for the foot bones' height and
  horizontal speed per source frame (the rig's mapping already names `left_foot` and `right_foot`).
- **A plant** is the first sampled frame of each run where a foot is within a tolerance of the clip's lowest foot point (a few
  per cent of the rig's height) and its height is no longer falling. For an in-place clip the planted foot slides back at the
  walk's speed, so speed alone won't do; with root motion, also require the speed near zero. Record the tolerance chosen.
- `clips.json` gains, per clip, `events: {"foot": [frame, ...]}`: indexes into the clip's game frames (its `frames` list),
  sorted. A clip with no plant (idle) has `"foot": []`. Bump `CLIPS_SCHEMA_VERSION`.
- `character.json` carries each clip's `events` as they are (export's `schema_version` bump). The SpriteFrames are unchanged:
  Godot has no frame events there; the game reads `character.json`.

## Acceptance criteria

- [ ] CLI seam, on the fake Blender: a walk whose fake foot heights touch the ground twice gives two `foot` frames, and an idle
      none; the events reach `character.json`.
- [ ] Marked `blender` test on the fixture rig: a two-step clip gives two plants.
- [ ] On mc02: walk and run's `foot` frames, laid out as a strip with the plants marked, checked by eye; path listed here.

Budget: 100–180k tokens.
