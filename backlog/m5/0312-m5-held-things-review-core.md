---
status: todo
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

- [ ] CLI seam: a character made from a base whose clip holds a thing builds `clips` and lists the thing; a stray file in
      `src/things/<id>/` is no thing at `decide`; two hand-laid Variants give the same current file in `show` and `render`;
      a `.glb` with two unnamed materials numbers both; a bad socket on a based character is refused at `decide`.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
