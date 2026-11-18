---
status: done
milestone: M5
agent: godot-export
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0243-m5-portrait-recipe.md]
---

# M5: export a portrait set

Spec §9. Part of [0240](0240-m5-portrait-kind.md).

## What to build

- The portrait's `export` Stage leaves `<emotion>.png` per emotion and `portrait.json` in `out/export/`: `schema_version`,
  `asset`, `canvas`, `anchor`, `fallback`, and `emotions` (ID and file, in the Decisions' order).
- The Exporter writes them under `portraits/<asset>/` beside the other exports, with no scene: the game's portrait UI loads
  the PNGs and reads `portrait.json`.
- **The Manifest:** the emotion IDs are exported IDs in their own list, frozen once exported. A `remove` or `rename` of an
  exported emotion is refused before it's recorded, as a Loop's is.
- **Checks:** every image is the canvas's size, with the same anchor (`export.portrait_canvas`); the fallback names an
  emotion of the set; binary alpha.

## Acceptance criteria

- [x] CLI seam: a built portrait exports one PNG per emotion and `portrait.json`, and the Manifest lists the emotions.
- [x] A rename of an exported emotion is refused. Adding an emotion after export is fine.
- [x] Spec §9 gets a Portrait row.

## Result

- **Stage** (`kiripix/recipes/portrait.py`): `export` builds `neutral.png`, `<id>.png` per emotion and `portrait.json`
  (`schema_version` 1: `asset`, `canvas`, `anchor`, `fallback`, `emotions` as `{id, file}`, `neutral` first). Its Checks:
  `export.no_target`, `export.portrait_canvas` (size, and the Grid's anchor is the brief's), `image.partial_alpha`,
  `portrait.fallback_unknown`. **Version bump:** `export` 1 to 2 (it was a stub, as the icon's was).
- **Exporter** (`kiripix/export/portrait.py`, `_portrait_files`): `portraits/<name>/`, no scene, byte for byte. The reader
  `read_portrait` follows `read_icon`; the Kind is in `_FILES_BY_KIND` and `EXPORTERS`, with no new switch on its name in
  `export/__init__.py`.
- **Manifest:** `ids.emotions` (the declared emotions, not `neutral`), left out of the file when empty like `states` and
  `links`, so every existing Manifest is unchanged byte for byte and still reads; no `schema_version` bump and no migration
  (an older Kiripix refuses a Manifest that has it, as for `states`).
- **Freeze:** `frozen_findings` covers emotions (`_current_ids` reads the Decisions); `emotion_freeze_findings` refuses an
  `emotion_remove` or `emotion_rename` of an exported emotion on `decide` and `redo` (`export.id_frozen`). Adding is fine.
- Spec §9 has the Portrait row; §6.7's `export` row is updated. Tests: `tests/cli/test_export_portrait.py`.

### Review fixes (2026-11-18, main session)

- `export.portrait_canvas` could never fail on the anchor (`fit` copies the brief's). It now warns when the fitted neutral
  figure stands more than a pixel off the anchor (an Owner's crop offset, or a source too small to reach it).
- `emotion_freeze_findings` uses `is_portrait`. `read_built_record` moved to `kiripix/export/built.py` with `EXPORT_STAGE`
  and `built_dir` (re-exported by `export/room.py`). Prop's `NO_TARGET` and `export_needs_input` are public, as the icon and
  the portrait use them.
- No Manifest `schema_version` bump for `ids.emotions` (the Owner, 2026-11-18): the key is optional, an older Manifest reads as
  it did, as with `states` and `links`.
