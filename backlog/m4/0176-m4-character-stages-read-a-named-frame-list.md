---
status: todo
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

- [ ] Every existing character test and golden passes unchanged, and `character.mc02`'s Stages stay `done` after the change
      (no input hash changed): checked with `kiripix status` on a copy of the art Project.
- [ ] CLI seam on the fake renderer: `finish normals=flat` and `normals=height` write a normal frame of the colour frame's size;
      `flat` is (128, 128, 255) on every opaque pixel.
- [ ] A test frame list with `feet` makes `sheet.pivot_drift` report the frame whose feet moved, and not one whose pivot alone
      differs.
- [ ] `uv run lint-imports` and `uv run mypy` pass.

Budget: 80–120k tokens.
