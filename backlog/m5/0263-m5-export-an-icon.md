---
status: done
milestone: M5
agent: godot-export
type: ticket
parent: 0253-m5-icon-kind.md
depends_on: [0262-m5-icon-kind-and-stages.md]
---

# M5: export an icon

Spec §9. Part of [0253](0253-m5-icon-kind.md).

## What to build

- The icon's `export` Stage leaves `icon.png` and `icon.json` (`schema_version`, `asset`, `size`) in `out/export/`.
- The Exporter writes them to `icons/<name>.png` and `icons/<name>.json` under the export root, in the Manifest. No scene: the
  game's inventory UI loads the texture. The icon's ID is its Asset ID, frozen once exported, as any Asset's.
- `export --all` exports icons, and `--prune` removes a deleted one's files (with their `.import`, after
  [0250](0250-m5-m4-gate-small-findings.md)).

## Acceptance criteria

- [x] CLI seam: an icon exports both files, listed in the Manifest. A second export with nothing changed writes nothing.
- [x] Spec §9 gets an Icon row.

## Result

- `kiripix/recipes/icon.py`: the `export` Stage now copies `finish.png` to `icon.png` and writes `icon.json`
  (`schema_version` 1, `asset`, `size`) in `out/export/`. **StageSpec `version` bumped 1 to 2** (it was a stub that never
  completed, so nothing is stale in practice).
- `kiripix/export/icon.py` (`read_icon`, refuses an old `icon.json` with `export.icon_invalid`); `kiripix/export/__init__.py`
  `_icon_files`: `<root>/icons/<name>.png` and `.json`, byte for byte, no scene, empty ID lists (the Asset ID names the
  Manifest and is frozen as any Asset's). `icon` added to `EXPORTERS` and `_FILES_BY_KIND`; the "can't be exported" message
  names icons. `export --all` and `--prune` need no other change (the prune already removes `.import` sidecars).
- Spec §9 Icon row, §6.6 export row.
- Tests: `tests/cli/test_export_icon.py` (Stage outputs, Manifest and no-op second export, `--all`, changed file refused
  and `--force`, `--prune` with sidecar). No new Command, so no contract sample.
- Open: the shared `icons/` folder means two icons can't collide (names are unique per Kind), but an icon and the game's
  own `icons/<name>.png` are refused as unmanaged until `--adopt`.
