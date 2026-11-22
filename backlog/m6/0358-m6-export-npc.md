---
status: done
milestone: M6
agent: godot-export
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0356-m6-npc-kind-and-choose-stage.md, 0357-m6-npc-checks.md]
---

# M6: export an NPC as one appearance file the game's actor data names

Spec §9 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), to [0355](0355-m6-adr-npc-kind.md).
The game's side: `../urban-mystery-club/docs/TECHNICAL.md` ("Authored characters and NPCs") and its `CharacterSprite`'s
`set_colours`.

## What to build

- `export` writes `npc/<name>/npc.json` (`schema_version`, `asset`, `base`, `wearables` in stack order with each one's
  exported path, `colours` by Part: the choice's name and its ramp), in the Manifest under a frozen ID. No images: the game
  draws the base's and the Wearables' exports.
- Refused with `npc.base_not_exported` or `npc.wearable_not_exported` until each is in the game, as a Wearable is refused
  until its body is (`export --all` counts one exported in the same call).
- `--prune` removes a deleted NPC's file.
- A note for the game in the Result: the file's fields and how `set_colours` reads `colours`.

## Acceptance criteria

- [x] CLI seam: a test NPC exports its file, in the Manifest; a missing base export is refused; `--prune` removes it.
- [x] Spec §9's NPC row.

## Result

No Stage `version` bump: the `npc` `export` Stage is new (it was declared, not built). No schema bump: `npc.json` of `choose` is unchanged;
the game's file is a new format, `schema_version` 1.

- **The Stage** (`run_npc_export` in `kiripix/recipes/npc.py`): checks and copies `choose`'s `npc.json` to `out/export/`; `needs_input` and
  `check` are the character's (`export.no_target`). `StageSpec.checks` also lists `npc.base_not_exported` and `npc.wearable_not_exported`
  (checked when exporting, as `wearable.body_not_exported` is). It declares no `check_reads` (it reads only `choose`'s output).
- **The Exporter** (`kiripix/export/npc.py`, `_npc_files` in `kiripix/export/__init__.py`, `npc` added to `EXPORTERS`): writes the one file
  `npc/<name>/npc.json`. It follows the Wearable's precedent: an NPC is exported after the others of the call (`_EXPORT_RANK`), and a base
  or Wearable counts as in the game when its Manifest says exported or when the same call is about to write its scene. Every missing one is
  a finding (exit 1), each with `fix: kiripix export <id>`. `export_pending` treats those refusals as "pending". The ID is the Asset ID
  (frozen by the Manifest's name, as an icon's is); no other ID is exported. `--force`, `--adopt` and `--prune` are the shared ones.
- **A note for the game.** `npc/<name>/npc.json` under the export root, LF, 2-space JSON, byte-identical for the same choice:

      {"schema_version": 1, "asset": "npc.guard",
       "base": "character.body_m", "base_path": "res://kiripix/character/body_m/body_m.tscn",
       "wearables": [{"id": "wearable.hair_a", "order": 10, "path": "res://kiripix/wearable/hair_a/hair_a.tscn"}],
       "colours": {"hair": {"choice": "auburn", "rgb": [[r, g, b], ...]}}}

  `wearables` run bottom to top (stack the base, then each in this order; `order` is the NPC's own, which may differ from the Wearable's
  default). `path` is the exported scene to instance. `colours` is by Part (a row of the Project ramp table, the same names as the
  base's `character.json` `parts`): `rgb` is the ramp, dark to light, 0-255 per channel, `length` as long as the Part's ramp. For
  `CharacterSprite.set_colours(choices: Dictionary[String, PackedColorArray])` build `choices[part] = PackedColorArray` of
  `Color8(r, g, b)` for each `rgb` step (`choice` is only the name, for the game's own use); a Part not listed keeps the colours the body
  was built with.
  The base's `ramps.png` has a row for every Part of the table, so every Part of `colours` fits it.
  `set_colours` returns false (nothing changed) when a ramp's length doesn't fit the body's, so a game test can load every `npc.json`.
- Spec §9's NPC row updated. Test: `tests/cli/test_export_npc.py` (one built NPC: refused with neither, then with the base only, then
  `export --all` writes Wearable and NPC in one call; the file's content; no image; Manifest; byte-identical rebuild; `export.file_changed`;
  `--prune`).
- Left out: `--force`/`--adopt` for the NPC file have the shared code path, which `test_export_wearable.py` already covers; no ID of a Part
  or of a Wearable is frozen in the Manifest (the game's `npc.json` names them, and the Wearables' own Manifests freeze their IDs).
