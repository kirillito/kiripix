---
status: todo
milestone: M6
agent: godot-export
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0344-m6-mask-add.md]
---

# M6: export every painted Mask, not only `solid` and `pit`

Spec §9 (Room, "Masks and `room.json`") and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md).

## The gap

The room's export copies `masks/solid.png` and `masks/pit.png` and lists them in `room.json`. A named Mask
([0344](0344-m6-mask-add.md)) is built by `masks` but never reaches the game.

## What to build

- Every painted Mask of the room's view is copied to `masks/<name>.png`: 1-bit, the room's size, byte for byte, as `solid`
  is now. Each is in the Manifest.
- `room.json`'s `masks` lists each Mask: `name`, `file` and `meaning` (from `kiripix.toml`), with `collision` only for
  `solid` and `pit`. That is a `schema_version` bump. No scene node is made for a named Mask: the game reads the PNG for its
  grid, as it does `solid.png`.
- **Frozen names:** the Mask names a room exported go in its Manifest's `ids.masks`, frozen once exported. The game's grid
  reads them by file name, so a renamed Mask is refused (`export.id_frozen`), as Marker IDs are. That is a Manifest schema
  bump; an older Manifest reads as having none, as the schema 3 change did.
- The export Stage's `version` bumps, named in the Result. Don't run alongside [0342](0342-m6-export-room-normals.md): both
  bump `room.json`.

## Acceptance criteria

- [ ] CLI seam: a test room with `cover` painted exports `masks/cover.png` and lists it in `room.json` with its meaning, and
      in the Manifest's files and `ids.masks`.
- [ ] CLI seam: removing an exported Mask from `kiripix.toml` and exporting is `export.id_frozen`.
- [ ] Headless Godot: `Texture2D.get_image()` on `masks/cover.png` gives the painted pixels exactly.
- [ ] Spec §9 and the Manifest section updated.
