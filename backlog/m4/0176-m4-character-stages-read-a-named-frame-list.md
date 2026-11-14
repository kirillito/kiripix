---
status: done
milestone: M4
agent: character-pipeline
type: ticket
parent: 0174-m4-sprite-kind.md
depends_on: [0150-m4-palette-ramps-per-part.md, 0168-m4-palette-reads-the-ramp-table.md]
---

# M4: the character's `palette`, `finish` and `sheet` read the frame list from a named Stage

Spec §6.3. Part of [0174](0174-m4-sprite-kind.md). The `sprite` Recipe ([0179](0179-m4-sprite-recipe.md)) reuses these Stages
unchanged, so they must stop assuming that the frame list comes from a Stage named `render`. Comes after
[0150](0150-m4-palette-ramps-per-part.md) and [0168](0168-m4-palette-reads-the-ramp-table.md), which edit
`character_palette.py` and the `render.json` contract.

## What to build

- `run_character_palette`, `run_character_finish`, `run_character_sheet` and their checks take the name of the Stage that holds
  `render.json` and the colour frames (the character: `render`; a sprite: `fit`), for example as a factory that returns the
  StageSpec's `run` and `check`. Nothing is read from `run.upstream["render"]` by a literal name any more.
- `finish` gains a `normals` parameter: `pass` (today's behaviour: the normal pass from the frame-list Stage, the character's
  default), `height` (`normals_from_height` on `height_from_alpha`, from [0177](0177-m4-sprite-ops.md), with an optional share
  of the colour frame's lightness, `relief`, 0 to 1, default 0) or `flat` ((128, 128, 255) on every opaque pixel). Either way
  the result is quantised to `normal_levels`, encoded and cut by the final colour frame's alpha, exactly as today. The
  character's `normals` defaults to `pass`, so its parameters, inputs and outputs are unchanged and nothing rebuilds.
- The frame list's per-frame entry may carry `feet` (`[x, y]`, measured). `sheet.pivot_drift` compares `feet` when it's there,
  and `pivot` otherwise. A character's `render.json` has no `feet`, so its check is unchanged.

## Acceptance criteria

- [x] Every existing character test and golden passes unchanged, and `character.mc03_female` and `mc03_male` Stages stay `done`
      after the change (no input hash changed): checked with `kiripix status` on a copy of the art Project (mc02 is retired).
- [x] CLI seam on the fake renderer: `finish normals=flat` and `normals=height` write a normal frame of the colour frame's size;
      `flat` is (128, 128, 255) on every opaque pixel.
- [x] A test frame list with `feet` makes `sheet.pivot_drift` report the frame whose feet moved, and not one whose pivot alone
      differs.
- [x] `uv run lint-imports` and `uv run mypy` pass.

Budget: 80–120k tokens.

## Notes (2026-11-12)

- The factories are `palette_stage(frames)`, `finish_stage(frames)` and `sheet_stage(frames)`, each returning `(run, check)`; the
  character's `run_character_*` and `check_character_*` are `...("render")` / `("finish")`, so `character.py` is unchanged.
  `normals_params(default)` gives the `normals` and `relief` ParamSpecs for a Recipe that declares them; the character does not
  (a declared default is hashed), and its `finish` reads `pass` when the parameter isn't declared. `flat` is written as the
  encoded value on the final colour frame's opaque pixels, not quantised again (8 levels would turn (128, 128, 255) into a tilt).
  `sheet` takes the expected frame counts from the frame list when the Recipe has no `clips` Stage.
- The character's Stage specs (inputs, params, Checks) are identical before and after, so no input hash can change.

## Notes (2026-11-13): first box checked on mc03

- Copied `kiripix.toml`, `style/` and the four `mc03_*` Assets of the art Project to temporary folders, and ran `kiripix status`
  with the code at `f6a6d0d^` (before 0172 and 0176) and at `f6a6d0d` (after).
  `mc03_female` and `mc03_male`: `model` to `sheet` are `done` in both. The 0176 Stages (`palette`, `finish`, `sheet`) did not change a hash.
- `export` went from `stale` to `done` between the two, because of 0172 (`character.json` schema 4, clip `events`), not 0176.
  The Assets were last built with code from after that commit.
- At the current tree `render` is `stale` on `mc03_female` and `mc03_male` (and everything after it). That comes from later changes
  to `render.py` (the Render material pass, 0148 and after), not 0176. `mc03_*_clothes01`, built with the current tree, are `done`
  through `export`.
- Both runs print `config.invalid` twice on the partial copy of the art Project. I didn't look into it; it appears in the before and after runs alike, so it isn't 0176.
