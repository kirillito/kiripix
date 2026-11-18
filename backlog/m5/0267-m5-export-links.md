---
status: done
milestone: M5
agent: godot-export
type: ticket
parent: 0255-m5-traversal-links.md
depends_on: [0265-m5-link-marker.md]
---

# M5: export Links

Spec §9 (Room). Part of [0255](0255-m5-traversal-links.md).

## What to build

- In the room's scene, a `Links` node with one `Node2D` per Link, named by its ID, holding two `Marker2D` children, `from` and
  `to`, at the ends. The Link's node has metadata `kiripix_id`, `kiripix_type = "link"`, `kind` and `two_way`.
- `room.json` (bump `schema_version`) gets `links`: ID, kind, `from`, `to`, `two_way`.
- The Manifest lists the Link IDs in their own list, frozen once exported.

## Acceptance criteria

- [x] CLI seam: a room with a one-way and a two-way Link exports both nodes, with their metadata and ends, and `room.json`
      lists both.
- [x] A rename of an exported Link is refused.
- [x] Spec §9's Room row describes Links.

## Result

- **Scene** (`kiripix/export/godot.py`): after `Emitters`, a `Links` node (only when the room has a Link) with a `Node2D` per
  Link, named by its ID (dots as `-`), ordered by ID, at the origin, with metadata `kiripix_id`, `kiripix_type = "link"`, `kind`
  and `two_way`, and `Marker2D` children `from` and `to` at the ends in room pixels. A room with no Link has the scene it had.
- **`room.json`** (`kiripix/recipes/room.py`): `schema_version` 11, with `links` (`id`, `kind`, `from`, `to`, `two_way`, by ID).
  An older rebuilt `room.json` is refused by the existing check, naming `kiripix run <room> export --force`. The `export`
  Stage is `version` 2 (ticket 0278), so the Owner's rooms show it stale and rebuild it. The tests that assert the version (10 to 11) were updated.
- **Manifest**: `ids.links`, its own list, left out of the file when empty (so no Manifest schema bump and no change to an
  Asset without Links); merged by union. The freeze (`export.id_frozen`, noun "Link") reads the IDs from the `place` Stage's
  Decisions, so a rename or removal fails before anything is run again.
- **Tests**: `tests/cli/test_export_links.py` (8), against a temporary Godot project. Spec §9's Room row describes Links.
