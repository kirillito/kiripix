---
status: todo
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

- [ ] CLI seam, on the fake Blender: `render points=...` puts each point in every frame of `render.json` and in
      `character.json` relative to the pivot. Without the parameter both files are byte-equal to today's.
- [ ] An unknown bone gives `render.point_unknown`, listing the bones. A bad name is refused with a fix.
- [ ] On a real character in a scratch Project (mc03_male_clothes01's `phone` clip, or `idle` until it exists): `hand_r`
      drawn as a dot on the sheet at 4x sits on the hand in all 8 directions. The sheet's path is recorded here for the Owner.
- [ ] Spec §6.3 (render) and §9 (Character) say what's recorded and exported. `uv run lint-imports` and `uv run mypy` pass.
