---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: `sprite` effect parameters

Spec §6.4 and §14 (M6). From the trial [0347](0347-m6-vfx-trial.md): a battle effect is a `sprite` with parameters. The trial
ran effects through `new`, `set`, `import --role sheet`, `run` and `export` and found these gaps. The Owner chose `sprite` with
parameters on 2026-11-20; `vfx` stays in Later.

## What to do

- A `fit` parameter `anchor`: `feet` (the default, as now), `centre`, or `x,y` in the frame's pixels. An effect's pivot is its
  own anchor, not a figure's ground point (the trial's spark, telegraph and cone got (11,18), (16,29) and (73,59)).
- With `finish` `outline=false` the cell takes no spare pixel for the outline (a 32 px cell stays 32).
- An effect mode (a `fit` parameter `effect`, default false): `fit.height` and `palette.sprite_regions` stay quiet, and
  `normal.png` is not written (the sprite is flat).
- A clip may end on a blank frame (`sheet.empty_frame` is a warning, not an error, in effect mode).
- A `clip` Decision takes `ticks` (a list of per-frame durations in ticks, as a Loop's), so a Pixelbolt render's frame
  durations are kept; `fps` stays the default.
- A new parameter at its default is no rebuild; a changed default or a changed output bumps the Stage's `version`, named in
  the Result.

## Acceptance criteria

- [x] A 24 px spark and a 32 px telegraph keep their size and centre, and `character.json`'s pivot is the anchor.
- [x] Without `effect`, every existing sprite builds as before, byte for byte.
- [x] A one-shot ending on a blank frame builds with a warning.
- [x] Tests at the CLI seam and a golden for the cell and pivot; `lint-imports` and `mypy` pass.

## Result

Done 2026-11-21. Spec §6.4 has a paragraph "Effect parameters".

- **`fit anchor`** (str, default `feet`): `feet`, `centre` (the middle of each direction's first fitted frame, `w // 2, h // 2`) or
  `x,y` in the fitted frame's pixels. A `pivot` Decision still wins. A bad value fails `fit` with `fit.anchor_invalid`. The pivot is
  `render.json`'s `pivot`, so `character.json`'s top-level `pivot` and each clip's `pivot` (`{"x", "y"}` from the cell's top left)
  are the anchor; there is no separate `anchor` key in `character.json` (0364: read the `pivot`).
- **`fit effect`** (bool, default false): the cell is every frame's whole area around the anchor, not the opaque box (blank frames
  count), plus the 1 px spare; `render.json` and `fit.json` say `effect: true`, and `sheet.json` too. `fit.height` and
  `palette.sprite_regions` are quiet; `sheet.empty_frame` is a warning.
- **`finish outline=false`** in effect mode cuts the spare pixel again (colour and normal frames, `render.json`'s `frame`, `pivot`,
  frame pivots and feet), so a 24 px spark stays 24 and a 32 px telegraph 32. Without `effect` the spare pixel stays as before.
  (`fit` cannot read `finish`'s parameters, so `finish` reads `fit`'s `effect` from its upstream parameters.)
- **No `normal.png`:** in effect mode the `export` Stage copies no normal atlas, `character.json`'s `files` is `{"color": ...}`, and
  the Godot export writes a CanvasTexture with the diffuse alone. The `sheet` Stage still packs its own `normal.png` internally.
- **`clip` Decision `ticks`:** a list of integers >= 1, one per frame, 60 a second. They go to `frames.json`, `render.json`,
  `sheet.json` and `character.json` on the clip (`clips[].ticks`, only when decided); `fps` stays the default or what was decided.
  `clips.ticks_count` (error) when a direction's frame count differs. The Godot `frames.tres` still gives every frame a duration of
  1.0: using the ticks there is 0364's.
- **Version bumps: none.** Every new parameter and key is written only when asked, so an existing sprite's outputs and input hashes
  are unchanged (a test builds a sprite, sets the parameters to their defaults, and finds every `work/` file byte for byte and `fit`
  still `done`). `character.json` stays schema 7 (optional keys, as `points`).
- Tests: `tests/cli/test_sprite.py` (the effect tests at the end), `tests/golden/test_sprite_effect.py` (golden
  `sprite_effect_cell_pivot.png`: the cell of a 12 px spark, enlarged, the pivot dotted).
