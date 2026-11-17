---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: `render` records named points per frame, and `character.json` exports them

Spec §6.3 (render, export) and §9 (Character). Part of [0236](0236-m5-the-games-next-needs.md), item 1. The game's
`docs/backlog/m3/0072-m03-clips-and-directions.md` ("The phone in the hand") and DEC-068.

## The gap

The game's MC idles looking at a phone, and nothing can put the phone in the hand yet (trial
[0238](0238-m5-held-things-trial.md)). The game's fallback draws a 2–3 px phone at the hand, per frame and direction. Today
that means a table measured by eye. The same points would give the game its VFX origins (the trumpet's notes, a cast), the
hit flash and a speech-bubble anchor.

`render` already reports where each eye is in every frame, from the posed mesh (`eyes`, ticket 0203). A bone or an empty can
be reported the same way.

## What to build

- **`render points=<list>`**: each entry names a point for the game and what it follows, which is a bone of the Model's
  armature or an empty in the Model, by name. The format is the implementer's (for example
  `hand_r@mixamorig:RightHand,head@mixamorig:Head`), and so is the name check (`[a-z][a-z0-9_]*`). A bone gives its head. An
  empty parented to a bone (a socket, such as a grip) gives its own place, so a Model can put a point exactly where the game
  wants it.
- For every frame of every clip and direction, Blender writes each point's place in render pixels (sub-pixel), its depth,
  and `hidden` when the depth pass has the body in front of it, as `posed_eyes` and `seen_eyes` do for eyes.
  `render.json` gets `points` (the list) and each frame a `points` map. Nothing is written when the parameter is empty, so
  existing characters' `render.json` is byte-equal.
- **With a base** (ADR 0012): the parameter falls back to the base's like any other, and a bone name is checked against
  the character's armature. A missing bone or empty is a finding that lists the armature's bones (`render.point_unknown`).
- **Export:** `character.json` (bump `schema_version`) gets, per clip, direction and frame, `points`:
  `{name: {x, y, hidden}}` in whole pixels relative to the pivot (y down, as Godot draws). The `sheet` Stage carries
  them from `render.json`. The `.tres` and the scene don't change: the game reads the points from `character.json`.
- A transition clip (0218) and a `still` clip get points like any other. With `speed`, they follow the subsampled frames.

## Out of scope

- Points on a `sprite` (it has no bones). If the game needs them for a creature, a `point` Decision per frame is a later ticket.
- Drawing anything at a point.

## Acceptance criteria

- [x] CLI seam, on the fake Blender: `render points=...` puts each point in every frame of `render.json` and in
      `character.json` relative to the pivot. Without the parameter both files are byte-equal to today's.
- [x] An unknown bone gives `render.point_unknown`, listing the bones. A bad name is refused with a fix.
- [x] On a real character in a scratch Project (mc03_male_clothes01's `phone` clip, or `idle` until it exists): `hand_r`
      drawn as a dot on the sheet at 4x sits on the hand in all 8 directions. The sheet's path is recorded here for the Owner.
- [x] Spec §6.3 (render) and §9 (Character) say what's recorded and exported. `uv run lint-imports` and `uv run mypy` pass.

## Result

- `render points=<name>@<target>,...` (`kiripix/recipes/render.py`, `kiripix/blender/render_frames.py`): a bone gives its head, an
  Empty its own place. Each frame of `render.json` gets `points`: `{name: {x, y, depth, hidden}}` in render px; the top level
  gets `points` (the entries). Nothing is written without the parameter and the clip keys don't change, so the old
  `render.json` is byte-equal. The parameter falls back to the base's like any other. A malformed entry or name is
  `render.point_invalid` (fix: clear the parameter); a missing target is `render.point_unknown`, listing the bones and Empties.
- `sheet` carries each frame's points relative to the pivot as `floor(render x - rounded pivot x)`, y down (the pixel that holds
  the point). `character.json` is `schema_version` 5 only when a frame has points, and then each frame has `points`
  `{name: {x, y, hidden}}`; otherwise it stays version 4 and byte-equal to today's. The reader takes 4 and 5. The ticket asks
  both for a bump and for byte-equality, so the version follows the content; if the Owner prefers always 5, it is one line in
  `character_export.py` and the two tests that read `schema_version: 4`.
- `hidden`: the depth pass has the body nearer than the point by more than 8% of the Model's height (`HIDDEN_MARGIN`), since a
  bone's head lies inside the body. A bone deep in a thick part (the head bone, at the neck) reads hidden in most views; an Empty
  on the surface is exact.
- Fake Blender: bones `hips`, `hand_r`, `head` (file `blender-bones` overrides); tests in `tests/cli/test_character_points.py`.
- Real character, in a scratch Project (a copy of urban-mystery-club-art's `mc03_male`, whose Mixamo rig is that of
  `mc03_male_clothes01`; the latter currently fails `rig.model_mismatch` in the Owner's Project, unrelated), `idle` as a still,
  `points=hand_r@mixamorig:RightHand,head@mixamorig:Head`: the sheet at 4x with `hand_r` (red) and `head` (green) drawn from
  `character.json` is `C:\Users\Kirill\AppData\Local\Temp\claude\e7ccd5c4395c2f79\849dd974-299e-4135-8401-aad27f459dd2\scratchpad\mc03_male_points_4x.png`. The red dot sits on the right hand (screen left of the body from the front) in all 8 directions.
  The first frame of each direction is the first of each group of four cells.

### The Owner's choices (2026-11-17)

- `character.json` keeps `schema_version` 4 when no frame has points and writes 5 when one does, so a character without
  `points` stays byte-equal. The reader accepts both.
- `hidden` keeps its margin (8 % of the Model's height, `HIDDEN_MARGIN`). A bone's head lies inside the body, so it reads hidden
  in many views; a point the game needs `hidden` for should be an Empty on the surface, parented to the bone.
