---
status: todo
milestone: M4
agent: godot-export
type: ticket
parent: 0127-m4-rooms-for-grid-battles.md
---

# M4: the Masks as images, and `room.json`, in the game

Spec §9 (Room). The game builds its battle grid from the room's `solid` Mask, from plain data, never from Nodes (its TECHNICAL
§4.5). Today only the scene, the Plate and the Layer PNGs reach the game ([export/__init__.py](../../kiripix/export/__init__.py),
`_room_files`). `room.json` stays in `out/export/`, and its collision shapes are simplified by `tolerance`, so rebuilding cells
from them is lossy at a cell's edge.

## What to build

- The room's `export` Stage copies the `solid` and `pit` Masks into `out/export/masks/`, and the Exporter writes them beside the
  scene as `masks/solid.png` and `masks/pit.png`: 1-bit, at the room's size. `room.json` goes beside them, and lists the Mask files.
- Once Looks are exported ([0123](0123-m4-looks-export.md)), each Look's own `solid` goes in the same folder as
  `masks/<look>.solid.png`.
- The scene's root gets `metadata/kiripix_room` with the `res://` path of `room.json`, so the game finds everything from the scene.
- The Manifest lists the new files, so ownership, `--force`, `--adopt` and `--prune` apply to them.
- Spec §9: the game reads a Mask with `Texture2D.get_image()` (Godot's default lossless import keeps the pixels exact), or from
  `room.json`'s paths with its own loader.
- `room.json` is now part of the game's contract. The Owner accepts schema changes until there are production rooms
  (2026-11-08), and a schema change means a re-export.

## Acceptance criteria

- [ ] CLI seam: the files exist, the Masks are pixel-equal to the `masks` Stage's output, and the Manifest lists them. `--prune`
      removes them.
- [ ] A `godot` test reads `masks/solid.png` in a headless Godot 4.7 and counts the same set pixels as Kiripix.

Budget: 150–250k tokens.
