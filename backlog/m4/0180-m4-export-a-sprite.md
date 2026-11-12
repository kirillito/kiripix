---
status: done
milestone: M4
agent: godot-export
type: ticket
parent: 0174-m4-sprite-kind.md
depends_on: [0179-m4-sprite-recipe.md]
---

# M4: export a sprite as a character

Spec §9 (Character), ADR 0003. Part of [0174](0174-m4-sprite-kind.md). The game loads a sprite with the loader it has for
characters, so a sprite's Godot files are the character's, made by the same functions.

## What to build

- `_FILES_BY_KIND` in `kiripix/export/__init__.py` gains `sprite`, through the character's path (`read_character`,
  `character_texture`, `character_frames`, `character_scene`); the files go to `<root>/sprite/<name>/`.
- The Manifest freezes a sprite's animation names (`<clip>_<dir>`) as it does a character's (`character_ids`); a sprite's
  frozen IDs gain nothing new, so the Manifest's schema doesn't change. `--prune`, `--force` and `--adopt` behave as for a
  character.
- `export.not_available`'s message lists sprites among what can be exported. Spec §9's table gains a Sprite row: "As a
  character, under `sprite/`."

## Acceptance criteria

- [x] CLI seam: a sprite's export writes `color.png`, `normal.png`, `texture.tres`, `frames.tres` and `<name>.tscn` into a
      temporary Godot folder; the `.tres` and `.tscn` text equals what the character functions write for the same
      `character.json`.
- [x] A 4-direction sprite's `frames.tres` holds exactly 4 animations per clip; removing a clip after export is refused as a
      frozen ID, as for a character.
- [x] Contract samples unchanged, or updated where `export`'s message changed.

Budget: 60–100k tokens.

## Notes (2026-11-12)

- Built: `sprite` in `_FILES_BY_KIND` (the same `_character_files`; the folder is `<root>/<kind>/<name>`, so `sprite/npc/`) and in
  `EXPORTERS`; one `_NOT_AVAILABLE` message ("only rooms, props, characters and sprites can") for both refusal sites. The Manifest
  schema is unchanged. Spec §9's table has the Sprite row.
- **Frozen sprite IDs are read from `frames.json`**, since a sprite's clips come from its sheets (a ZIP's folders), not from
  `clip` Decisions. So a clip taken away is refused once `frames` has run again; before that the freeze sees the old clips, and
  `export` stops with `export.not_ready` (the Stage is stale) with nothing written. A character's freeze fires at the Decision.
  Reading the ZIPs without running `frames` would duplicate the naming rule (and 0175 may still change it); left for the Owner.
- Tests: `tests/cli/test_export_sprite.py`. The "text equals what the character functions write" criterion is met by construction
  (one function, `_character_files`) and checked at the seam by the same assertions as a character's export (names, offsets, texture
  paths, 4 animations per clip, byte-identical re-export), not by importing internals. `test_sprite.py` asserted no refusal, so it
  needed no change. Contract samples unchanged. Opening the scene in a real Godot is not repeated for a sprite (same writers).
