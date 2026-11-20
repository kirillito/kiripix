---
status: done
milestone: M5
agent: godot-export
type: ticket
parent: 0254-m5-looks-markers-combining-and-reach.md
depends_on: [0314-m5-look-markers-on-place.md, 0315-m5-reach-per-look.md]
---

# M5: export a Look's Markers, collision and navigation

[ADR 0013](../../docs/adr/0013-a-look-has-its-own-markers-collision-and-reach.md), decisions 1, 2 and 4, and its
Consequences ("`room.json` schema 12", "The scene", "The Manifest", "What the game does"). Part of
[0254](0254-m5-looks-markers-combining-and-reach.md). Spec §9 (Room, Looks), §6.1 (`export`).

## What to build

- **Derived Masks:** per Look, `masks/<look>.added.png` and `masks/<look>.cleared.png` (1-bit, the room's size) from the
  Look's `solid` against the room's.
- **`room.json` schema 12:** the room's `markers` hold only its own. Each Look gains `markers` (as the room's entries),
  `navigation` (vertices, polygons and outlines, or `null` without its own `solid`; its walkable ∩ its reachable), and
  `added` and `cleared` beside `solid`, each a file and collision shapes. `masks` gains `<look>.added` and
  `<look>.cleared`. `collision.solid` stays the room's whole `solid`. An older `room.json` is refused, naming the rebuild.
- **The scene:**
  - the room's `solid` body is the room's `solid` minus every pixel some Look clears;
  - `LookSolids/<look>/added`, disabled; `LookSolids/<look>/cleared`, enabled, the pixels this Look alone clears;
  - pixels several Looks clear: one enabled body per set of Looks, with `metadata/kiripix_looks`;
  - a Look's whole-Mask body goes (its PNG stays);
  - `LookNavigation/<look>`, a `NavigationRegion2D`, `enabled = false`;
  - `LookMarkers/<look>`, a `Node2D`, `visible = false`, with the Look's metadata, holding its Markers with the room's
    node types (a light `enabled = false`), each with `metadata/kiripix_look`.

  With no Look shown, the scene collides exactly as before.
- **The Manifest, schema 3** (the Owner's change to the ADR draft): `ids.look_markers` lists `<look>/<marker>`, left out
  of the file when empty. `ids.markers` lists only the room's own. A schema 2 Manifest is migrated on read by a pure
  `migrate_v2` (`look_markers` empty), beside `migrate_v1` in `kiripix/export/manifest.py`, and rewritten once at the next
  export. Moving an exported Marker into or out of a Look is refused (`export.id_frozen`). `manifest merge` takes the union
  of `look_markers` and names a newer side as such.
- **Versions:** `export` 2 → 3.
- Spec §9: the Room row's Looks (what the game does to show a Look), `room.json` and the Manifest.

## Acceptance criteria

- [x] CLI seam: a room with a Look that erases part of `solid` exports a room body without that part, an enabled
      `LookSolids/<look>/cleared` body, and a disabled `LookNavigation/<look>`; with the Look hidden the collision is the
      room's as before.
- [x] Two Looks clearing the same pixels get one shared cleared body listing both in `metadata/kiripix_looks`.
- [x] A Look's light is under `LookMarkers/<look>` with `enabled = false`, and in `room.json` under the Look, not the room.
- [x] `room.json` has `schema_version` 12 and `masks` lists `<look>.added` and `<look>.cleared`.
- [x] The Manifest is schema 3 with `ids.look_markers`; a schema 2 Manifest reads, and the next export rewrites it. A room
      without Look Markers has no `look_markers` key.
- [x] Moving an exported Marker into a Look is refused (`export.id_frozen`). `manifest merge` unions `look_markers`.
- [x] Golden scene files updated with `--update-golden`, for the Owner to review. (New: there was no golden room scene; see Result.)

## Result

- **Built.** `room.json` is schema 12 (an older one is refused by `export.room_invalid`, whose fix is `kiripix run <asset> export
  --force`). Each Look has `markers` (the room's entries, without `look`), `navigation` (vertices, polygons, outlines, or `null`
  without its own `solid`: its walkable from `place` AND its reachable from `reach`, simplified at the export's `tolerance`) and
  `added` and `cleared` (`{file, collision}`, or `null`); `masks` gains `<look>.added` and `<look>.cleared`
  (`masks/<look>.added.png` is the Look's `solid` and not the room's, `.cleared.png` the room's and not the Look's; 1-bit, the
  room's size). The room's `markers` hold only its own. `collision.solid` stays the whole `solid`.
- **A new field, `scene`,** the shapes the scene's bodies need and the ADR left to the Exporter: `{solid, cleared: {<look>: shapes},
  shared: [{looks, collision}]}`: the room's `solid` minus every cleared pixel; each Look's own cleared pixels (those no other Look
  clears); one entry per set of two or more Looks, sorted by their IDs. With no Look clearing anything, `scene.solid` equals
  `collision.solid`.
- **The scene.** `LookSolids/<look>` is a `Node2D` (the Look's metadata) holding the `added` body (disabled polygons) and the
  `cleared` body (enabled); a `Shared_<look>+<look>` body under `LookSolids` per set, with `metadata/kiripix_looks`; the room's
  `solid` body is `scene.solid`. `LookNavigation/<look>` is a `NavigationRegion2D`, `enabled = false`; `LookMarkers/<look>` is a
  hidden `Node2D` with the Look's metadata, holding its Markers (a light `enabled = false`, each `metadata/kiripix_look`). A
  Look's lights take light textures after the room's (`light_<n>`), so the room's don't renumber. Rooms with no Look write the
  scene they wrote before (the new nodes appear only when needed).
- **The Manifest, schema 3.** `ids.look_markers` (`<look>/<marker>`, left out when empty); `ids.markers` lists only the room's. A
  pure `migrate_v2` (and `migrate_v1` then `migrate_v2` for a version 1) in `kiripix/export/manifest.py`; `export` rewrites a
  migrated Manifest once. The freeze compares both lists, so moving an exported Marker into or out of a Look is
  `export.id_frozen`. `manifest merge` takes the union of `look_markers`, and writes schema 3 (every Kind's Manifest goes to 3
  at its next export).
- **Versions.** `export` 2 to 3. Manifest 2 to 3. `room.json` 11 to 12.
- **Spec.** §9 (the Room row, `room.json`, what the game does to show a Look, the Manifest) and the §6.1 `export` row.
- **Tests.** `tests/cli/test_export_look_scene.py` (one per criterion, a byte-identical rebuild, and a Godot 4.7 one that loads the
  scene and reads the nodes back); `tests/cli/test_manifest_merge.py` (the union, the migration); a new golden-seam test
  `tests/golden/test_room_export_writers.py` with `tests/golden/expected/room_export/yard.tscn` and `yard_looks.tscn`. There was no
  golden room scene before, so no existing golden changed: the Owner reviews these two new ones. The schema numbers in
  `test_export*.py`, `test_emitter.py` and `test_export_character.py` went up.
- **Known limit.** Simplified shapes leave a seam of up to `tolerance` px where a cleared body meets the room's (the spec says
  so); tests compare areas within a slack, and the PNGs are exact.
