---
status: done
milestone: M4
agent: godot-export
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: the Masks as images, and `room.json`, in the game

Spec §9 (Room). The game builds its battle grid from the room's `solid` Mask, from plain data, never from Nodes (its TECHNICAL
§4.5). Today only the scene, the Plate and the Layer PNGs reach the game ([export/__init__.py](../../kiripix/export/__init__.py),
`_room_files`). `room.json` stays in `out/export/`, and its collision shapes are simplified by `tolerance`, so rebuilding cells
from them is lossy at a cell's edge.

## What to build

- The room's `export` Stage copies the `solid` and `pit` Masks into `out/export/masks/`, and the Exporter writes them beside the
  scene as `masks/solid.png` and `masks/pit.png`: 1-bit, at the room's size. `room.json` goes beside them, and lists the Mask files.
- Once Looks are exported ([0131](0131-m4-looks-export.md)), each Look's own `solid` goes in the same folder as
  `masks/<look>.solid.png`.
- The scene's root gets `metadata/kiripix_room` with the `res://` path of `room.json`, so the game finds everything from the scene.
- The Manifest lists the new files, so ownership, `--force`, `--adopt` and `--prune` apply to them.
- Spec §9: the game reads a Mask with `Texture2D.get_image()` (Godot's default lossless import keeps the pixels exact), or from
  `room.json`'s paths with its own loader.
- `room.json` is now part of the game's contract. The Owner accepts schema changes until there are production rooms
  (2026-11-08), and a schema change means a re-export.

## Acceptance criteria

- [x] CLI seam: the files exist, the Masks are pixel-equal to the `masks` Stage's output, and the Manifest lists them. `--prune`
      removes them.
- [x] A `godot` test reads `masks/solid.png` in a headless Godot 4.7 and counts the same set pixels as Kiripix.

Budget: 150–250k tokens.

## Result

- The room's `export` Stage copies the `solid` and `pit` Masks that exist byte for byte into `out/export/masks/`, and lists them in
  `room.json` as `masks` (`{"pit": "masks/pit.png", "solid": "masks/solid.png"}`, paths relative to `room.json`).
  `ROOM_SCHEMA_VERSION` is 5, so an old room needs `kiripix run <room> export --force`.
- The Exporter writes `room.json` and `masks/*.png` beside the scene; all are in the Manifest, so ownership, `--force`,
  `--adopt` and `--prune` apply. The scene root has `metadata/kiripix_room` with `room.json`'s `res://` path.
- [x] Done in [0131](0131-m4-looks-export.md): a Look's own `solid` is a further entry of `masks` (`<look>.solid`, file
  `masks/<look>.solid.png`), copied by the Stage and written by `_room_files` like the others. `ROOM_SCHEMA_VERSION` is 6 there.
- Left for the Owner: the `godot` test (`tests/cli/test_export_masks.py`) is written but was skipped here, as Godot 4.7 isn't
  on this machine; the second criterion stays unchecked until it has run.
- Tests: `tests/cli/test_export_masks.py`; counts and the `room.json` schema changed in `test_export*.py`, `test_emitter.py`.

## Closing notes (2026-11-13)

- The `godot` test (`tests/cli/test_export_masks.py`) passes against Godot 4.7.2 (headless unless noted), 2026-11-13.
