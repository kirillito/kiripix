---
status: done
milestone: M5
agent: core-engineer
type: ticket
---

# M5: held things, what the 2026-11-18 review found in core: a base's things, one rule for "a thing exists", one Variant

Left by the batch review of [0300](0300-m5-clip-attach.md), [0301](0301-m5-held-thing-import.md),
[0302](0302-m5-render-attached-things.md) and [0305](0305-m5-held-thing-colours.md). Better done before
[0304](0304-m5-export-cell-per-clip.md) puts held things in front of the game.

## What to fix

1. **A base's things.** The `clips` and `render` Stages take the base's `clip` Decisions (with their `attach`) but only
   `src/clips/*` from the base (`BaseInputs` in `kiripix/recipes/character.py`), not `src/things/*/*`. A character made from a
   base whose clip holds `phone` fails `clips.unknown_thing`. Take the base's things as base inputs (the Asset's own thing of
   the same ID wins), and let `show` list them with where they come from.
2. **One rule for "a thing exists".** `clips.thing_ids`, `held.asset_things`, `things.thing_ids` and `render._thing_files`
   disagree: the first two count any file in `src/things/<id>/` (a stray file or a `.materials.json` sidecar), the last two need
   a `.glb`/`.blend` Variant. `decide` accepts what `render` then refuses. One definition in `recipes` (Stages can't import
   core), used by all four.
3. **One current Variant.** Without an `imported.jsonl` record, `things.current` takes the newest by mtime and
   `render._thing_files` the last by name, so `show`'s material numbers and the material pass can disagree. One rule, shared.
4. **Unnamed `.glb` materials.** `things.glb_materials` collapses several unnamed materials into one `Material`; Blender numbers
   each (`Material`, `Material.001`). Count them as Blender does, so every later thing's `first` and `index` match the pass.
5. **A base's rig at `decide`.** `held.rig_bones` and `things.model_material_count` hard-code `work/rig/rig.json` and
   `work/render/render.json`. Resolve the Stage's output through `AssetGraph.output_dir`, so a character made from a base
   (its rig is the base's) gets `clips.unknown_socket` at `decide`, not only when the Stage runs.
6. **`attached_by` per thing.** `show._things` builds a new `AssetGraph` and re-reads the `clips` Decisions once per thing.
   Compute the attachment map once from `show`'s graph.

## Acceptance criteria

- [x] CLI seam: a character made from a base whose clip holds a thing builds `clips` and lists the thing; a stray file in
      `src/things/<id>/` is no thing at `decide`; two hand-laid Variants give the same current file in `show` and `render`;
      a `.glb` with two unnamed materials numbers both; a bad socket on a based character is refused at `decide`.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

Built, all six items:

1. A base's things: the `clips` and `render` Stages take `src/things/*/*` of the base as base inputs (`BaseInputs`), so a
   character made from a base whose clip holds `phone` builds `clips` and `render`. The Asset's own thing of the same ID wins,
   in the base's place; the base's come first in numbering order. `show` lists them with `from_base` (and "(base)" in the text).
   The base's `imported.jsonl` is read from its folder for the order and the current Variant, not hashed (adding it to the base
   inputs would make every based character's `render` stale); a base reimporting an existing Variant, which only moves its
   current pick, doesn't make a based character stale by itself.
2. One rule: `recipes.clips.held_things_of` (a `.glb`/`.blend` directly in `src/things/<id>/`), used by `clips.thing_ids`,
   `held.asset_things`, `things.thing_ids` and `render._thing_files`. A stray file or a `.materials.json` sidecar is no thing.
3. One current Variant: the newest import naming a file of the thing, else the last by name (no more mtime), in the same function.
4. `things.glb_materials` names duplicates as Blender does (`Material`, `Material.001`).
5. `held.rig_bones` and `things.model_material_count` resolve the Stage output through `AssetGraph.output_dir`; a based
   character whose own `rig` isn't built uses the base's rig, so a bad socket is `clips.unknown_socket` at `decide`.
6. `show` computes the attachment map once (`things.attachments(graph)`).

Tests: `tests/cli/test_held_things_review.py` (6 tests, one per acceptance item plus the own-wins case).

Stage version bumps: none. No Stage's output changes; a based character whose base has things now sees them as inputs, so its
`clips` and `render` are stale once, only if the base has things.

Left: ticket 0313's items (`_check_attach`, render.py, character_finish.py) untouched except the one-line `thing_ids` call in
`_check_attach`.

### Review follow-up (2026-11-18)

- **The base's `imported.jsonl` is hashed now.** `render` lists it in its base inputs (`BaseInputs.files`), as ADR 0012 requires
  for everything read from a base, so a re-import on the base makes a based character's `render` stale and it draws the new
  current Variant. The cost is ADR 0012's accepted one: any import on the base re-renders its characters once. ADR 0012's table
  now lists the base's things for `clips` and `render`, and the journal for `render`. New test:
  `test_a_re_import_on_the_base_makes_a_based_characters_render_stale_and_draws_the_new_current` (seen failing without the fix).
- Correction to the Result above: no Stage's *code* changed what it writes, but a based character whose base has things now
  renders them, so its `clips` and `render` outputs change once.
- `AssetGraph.base_asset` replaces the repeated `graph.base.asset if graph.base is not None else None`.
