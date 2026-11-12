---
status: done
milestone: M4
agent: character-pipeline
type: ticket
parent: 0147-m4-character-palette-ramps.md
depends_on: [0148-m4-render-material-pass.md, 0149-m4-part-ramp-ops.md]
---

# M4: the character `palette` Stage keeps a ramp per part

Spec §6.3 (palette, finish). Part of [0147](0147-m4-character-palette-ramps.md).

## What to build

- A `parts` parameter on the character's `palette` Stage: the swappable parts, each one material or several joined by `+`, such
  as `skin,hair,jacket+hood,jeans,boots`. A part may set its ramp length (`skin:4`); the default is `render.json`'s `bands`. A
  name that isn't a material of `render.json` fails the Stage with a finding that lists the materials. With no `parts`, the
  Stage does what it does today.
- With `parts`: the fixed materials get their subset (`colors` now counts only them), then each part gets its ramp with
  [0149](0149-m4-part-ramp-ops.md)'s Ops, and every frame is mapped by part. `palette.json` gains `parts` (name, materials,
  indexes and RGB, dark to light) and bumps its `schema_version`.
- The Stage's Checks add `palette.ramp_shared`.
- In `finish`: an `outline_colour` that is in a part's ramp fails the Stage with `finish.outline_in_ramp`, naming the part and a
  free index as the fix.
- `describe` shows `parts` with an example.
- Keep part names the key everywhere (in `palette.json`, in the Ops' arguments), not a part's position:
  [0166](0166-m4-ramps-match-across-characters.md) later fixes each part's length, row and colours across characters from a
  Project table.

## Acceptance criteria

- [x] CLI seam, on the fake: with `parts`, `palette.json` lists each part's ramp and no colour is in two; changing `parts` makes
      `palette` stale and leaves `render` alone; an unknown material fails with the list of materials.
- [x] `finish.outline_in_ramp` is raised and has a `fix`.
- [x] A sample in `tests/cli/test_contract.py` if a Command's output changes.
- [x] On mc02 with `parts=skin,hair,jacket+hood,jeans,boots`: every part has its own ramp. The 52 px frames are laid out
      before and after as a sheet for the Owner, with its path listed here.

Sheet for the Owner (mc02 rebuilt in a scratch copy, the art Project untouched; 52 px frames at x6, before on top, after below,
with each part's ramp): `C:/Users/KIRILL~1.BRE/AppData/Local/Temp/claude/2a77692328d6afa9/29d2099f-cc73-42f5-93b6-72d7e4586f4e/scratchpad/mc02-ramps-before-after.png`.
Note: `colors` is a ceiling; with `parts` it is also capped at the palette's size minus the ramps' lengths.
