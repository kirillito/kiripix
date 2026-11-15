---
status: done
milestone: M4
agent: character-pipeline
type: ticket
---

# M4: stamped eyes are painted on what covers them

Spec §6.3 (render, finish; M4 ticket [0203](0203-m4-stamped-eyes-blinks-and-still-clips.md)). Found in the generator
trial ([0164](0164-m4-claude-built-base-models-trial.md)), 2026-11-14.

## The gap

`render` records where each eye is from the posed mesh, and `finish` with `eyes=stamp` paints the eyes there. When
something is in front of the eyes, the stamp is painted on it. Seen on `character.npc_elder_coat` in the art Project (its
first build, a brimmed hat on a stooped head): in `walk_s` and `idle_s` the eye pattern sat on the hat's brim. At the 30°
look-down a brim wider than about 5 cm covers the eyes, and so can a fringe, a hood or a raised arm in a battle clip.

## What to build

- `render` records, per frame and eye, whether the eye shows: the material pass at the eye's place holds an eye
  material, not another one (it already writes that pass).
- `finish` doesn't stamp an eye that doesn't show in that frame.
- A Check (a warning), `sheet.eyes_covered`: a clip and direction whose front views (`s`, `sw`, `se`) hide both eyes in
  most frames, naming the material that covers them, so a hat that hides a face is caught before export.

## Acceptance criteria

- [x] CLI seam, on the fake: an eye behind another material gets no stamp in that frame; an eye that shows is stamped as
      today.
- [x] The warning names the clip, the direction and the covering material.

## Done

`finish` reads the material pass `render` already wrote, in a box the size of each eye's extent (at least its centre pixel):
an eye whose box holds no eye material, but another one, counts as not seen and gets no stamp (`_covered_by`, `_Eyes._anchor`
in `character_finish.py`). Nothing new is stored in `render.json`, so no Stage goes stale; `finish` needs `finish --force` to
drop stamps already painted. `sheet.eyes_covered` (warning, a `finish` Check, `check_eyes_covered` in `kiripix/checks/parts.py`)
looks at `s`, `sw` and `se`, frames where an eye faces the camera, and warns when all of those eyes are covered in more than half
of a clip direction's frames; it names the clip, the direction and the commonest covering material. Not on the sprite recipe.
Tests in `tests/cli/test_character_eyes.py`. Not run on real Blender or on `npc_elder_coat`.
