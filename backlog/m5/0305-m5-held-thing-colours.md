---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0302-m5-render-attached-things.md]
---

# M5: a held thing's colours: a ramp row for a class weapon, fixed colours for the rest

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **A class weapon gets a row in the Project's ramp table** (the Owner, 2026-11-18): its materials are a part (`stick`, `rake=rake+rake_head`,
  length 2), so its colours are its own and a skin or hair swap never reaches them. 0238: with a row, the body's fixed colours are
  identical to before (0 pixels differ); in fixed colours the palette re-chose 9 of the 16 fixed colours.
- **Anything else held** (the phone) takes fixed colours outside every part, and the fixed subset is chosen so a thing added later doesn't
  move the body's fixed colours (or a warning names the body pixels that moved).
- The `palette` and `finish` Checks tolerate a material absent from most clips (a thing appears only where attached).
- Stage `version` bumps where outputs change.

## Acceptance criteria

- [x] CLI seam: a fixture with a thing on a ramp row: the body's pixels in a clip without the thing are byte-identical before and after
      the thing is added; with fixed colours, a moved fixed colour is reported (by design none moves; what is reported is a thing left
      with no colour of its own, `palette.thing_colors_shared`).
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- **`recipes/character_palette.py`:** `material_indexes(render.json)` gives every material name and its indexes, the Model's first, then
  each thing's (`things[].materials`); a name shared by a thing and the Model, or two things, is one entry. `parts` may now name a thing's
  material (`stick`, `rake=rake+rake_head`), which joins the part and its table row like any material, so a class weapon never touches the
  body's colours. A thing's materials in no part are mapped apart from the body: the body's fixed subset is chosen from the body's pixels
  alone (so a thing added later moves none of its pixels, with or without `parts`), the ramps are fitted as before, and the things' own
  colours (`palette_subset` over their pixels, up to `colors`) come last, from the palette colours that no fixed colour, ramp or table row
  uses. Those pixels are mapped and orphan-cleaned as their own layer and put over the body's frame. `palette.json` (schema stays 4, additive)
  gains `thing_colors`, `thing_shares_body` and `thing_materials` only when such a thing is in a frame.
- **No moved colour to report:** the fixed colours of the body can't move, so the ticket's "or a warning names the body pixels that moved"
  is replaced by the guarantee. What can go wrong is a palette with no colour left for the thing: it then shares the body's fixed colours
  and the check gives `palette.thing_colors_shared` (a warning, owner action: add palette colours or give the thing a row).
- **Checks:** `palette.off_palette` allows `thing_colors`; `palette.ramp_shared` sees the things' indexes. A part or thing absent from a
  clip is nothing to find (the Checks read the material pass frame by frame).
- **`recipes/character_finish.py`:** `_InnerLines` reads the things' materials too, so `inner_lines=dark` draws a part's line colour on a
  thing in a part and a darker colour of its own on one outside, and `line_skip` can name a thing's material.
- **Stage versions:** `palette` is **2** (was 1), `finish` is **3** (was 2): both stale on every character (`render` is already stale from 0302).
- **Tests:** `tests/cli/test_held_colours.py` (fake Blender; `blender-thing-materials` in `tests/fixtures/kiripix_test_recipes.py` names a
  thing's material): a thing on a row maps to the row's colours; adding a second thing (in a new clip) leaves the other clips' frames and
  the body's colours byte-identical, and the thing gets colours outside the body's and the ramps; no colour left gives the shared warning;
  `finish` with `inner_lines=dark` and `part_lines` draws lines on the part, the row and the thing.
- Not done: the grip and look on a real Model (no real-Blender test of the colours; the fixtures' frames are flat colours).
