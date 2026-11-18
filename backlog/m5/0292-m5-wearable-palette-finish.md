---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0152-m5-character-layers.md
depends_on: [0291-m5-wearable-model-rig-render.md]
---

# M5: a Wearable's `palette` and `finish`, without an outline

Part of [0152](0152-m5-character-layers.md). From the trial [0153](0153-m5-character-layer-trial.md)'s Results and the Owner's answers (2026-11-18).

## What to build

- **`palette`:** the Wearable's parts get their own ramps, disjoint from the body's (M4's rule, 0147), so recolouring a Wearable
  touches nothing else. Hair styles reuse the `hair` Ramp; outfits use `top`, `under`, `bottom` and `shoes` (the game's fixed
  Parts).
- **`finish`: no outline in a Wearable** (the Owner, 2026-11-18): the game draws one outline on the stacked figure. A per-Wearable
  outline drew about 76 px of lines a frame inside the figure (13 % of it). The normal pass is aligned and quantised as the
  body's, never palette-mapped.
- The outline colour and width the game uses on the stack are the body's, already in `character.json`.

## Acceptance criteria

- [x] A Wearable's `finish` output has no outline pixels, and its ramps share no palette index with the body's (CLI seam).
- [x] `uv run mypy` passes.

## Result

- **`palette`** (`kiripix/recipes/wearable_palette.py`): the character's `palette` (same parameters, ramp table, parts, `part_lines`), run
  through `character_palette._run_palette`, which gained an `exclude` argument: the body's fixed colours and its parts' ramps
  (read from the body's `palette.json`) may be used by no fixed colour or fitted ramp of the Wearable. `palette` waits for the body's
  `palette` (`BodyInputs(built={"character": ["palette"]}, wait=True)`). A Project ramp table part whose colours the body's palette
  already uses, and that the Wearable names, is refused: `wearable.ramp_shared` (owner_action). Hair reuses the table's `hair` row
  when the body has none. The Check is the character's (`palette.off_palette`, `palette.ramp_shared`).
- **`finish`**: the character's `finish` with `outline`, `outline_colour`, `placement` and the eye parameters dropped (fixed off in
  `run_wearable_finish`), `inner_lines` limited to `off`/`dark`. The normal pass is the character's: aligned, quantised, never mapped.
  The outline colour and width the game uses are the body's (`character.json`), not read here.
- **Version bumps:** the Wearable's `palette` to 2 and `finish` to 3 (the first builds; 0290's were stubs). The character's `palette`
  and `finish` write the same as before (no bump).
- **Tests:** `tests/cli/test_wearable_palette.py` (waits for the body's palette, no shared index with the body's, finish adds no pixel
  and has no outline parameters); `test_wearable.py`'s stub test now looks at `sheet`.
