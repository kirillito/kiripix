# A Look has its own Markers, collision, navigation and reach

**Status: accepted** (2026-11-18, by the Owner, for ticket 0269, with one change: the Manifest's `schema_version` goes to 3
for `ids.look_markers`, with a migration. Drafted 2026-11-17; amends ADR 0009.)

ADR 0009 made a room's Looks a Stage on the room, and left open what a Look does beyond its picture (spec §16, open
decision 8). The code already went part of the way: a Look's `solid` Decision starts from the room's `solid`, and `erase`
clears it (`recipes/looks.py`, `SOLID_DECISION`), so a Look can take collision away as well as add it. Two rooms now need
the rest:

- **The laneway's back gate** (the M4 gate). `back_gate_open` has its own `solid` with the opening cleared. But `place` and
  `reach` read the room without its Looks, so `reach` reports the yard behind the gate, (58, 345), 463 x 274, as an
  unreachable island (`reach.unreachable_island`, warning). The exported navigation is walkable ∩ reachable, so the yard has
  no navigation even while the gate is open. The room is right, and the report and the navigation are wrong.
- **R6, the game's M10:** restoring the power lights the tunnel. That needs a Look that brings its own light Markers (and
  maybe emitters), and maybe two Looks shown at once (power on, and a gate open).

There is one more gap. Spec §9 tells the game to show a Look by enabling its `solid` polygons. A Look's `solid` is the
room's whole Mask with the Look's strokes, and the room's `solid` body stays enabled, so an `erase` never takes effect in
the game.

## The decisions

1. **A Look's own Markers.** A `marker` Decision on `place` may name a `look`. Only lights, emitters and interactables may
   name one. A Look's Marker is exported under the Look's nodes, hidden (a light also `enabled = false`), with the Look's
   metadata. `room.json` lists it under the Look, not in the room's `markers`. `place` checks it as it checks any Marker.
   Marker IDs stay one set over the room and its Looks (`marker.duplicate_id`), and a new Decision with the same ID and
   type moves a Marker into or out of a Look.
2. **Two Looks at once.** The game may show any number of Looks together. Kiripix doesn't know which ones it will. Where
   two Looks' regions overlap, `looks` warns (`look.overlap`, naming both), and the game decides which one draws on top.
   Collision combines by one rule: **a pixel any shown Look clears is clear, and a pixel any shown Look adds is solid**,
   against the room's `solid`. A Look can only clear where the room is solid and only add where it isn't, so no two Looks
   can disagree on a pixel, and the order doesn't matter. Kiripix exports each Look's change (added and cleared) as well as
   its whole Mask.
3. **`reach` per Look.** `reach` reports the room as now, and also each Look that has its own `solid`: the room's Spawns
   and Exits flooded over that Look's walkable. An island the room can't reach but some Look can is info, naming the Looks
   (`reach.island_under_look`), not a warning. The laneway's yard becomes info under `back_gate_open`.
4. **Walkable and navigation per Look.** `place` derives each such Look's walkable and clear Masks from the Look's `solid`
   and the room's `pit`. Export writes one `NavigationPolygon` per Look that has its own `solid` (its walkable ∩ its
   reachable), disabled, and the game swaps navigation when it swaps collision.

## We considered

- **For 2, declared combinations:** the Owner declares the Looks that show together, and Kiripix builds, checks, reaches
  and exports each combination as if it were one Look. It is the only option here that gives navigation and `reach` for
  two Looks that both change `solid`, at the cost of a new Decision, one more build per combination and a bigger scene.
  It was not chosen because no known room needs it: the laneway's gate and R6's lights have one `solid`-changing Look
  each. It stays open (below).
- **For 2, one Look at a time:** simplest, but R6 already wants power on together with a gate open.
- **For 1, Markers in the game's data:** the game would place a Look's lights itself, off the painting and outside the
  `place` Checks, which is the split ADR 0009 avoided for pictures.

## Consequences

- **The graph.** `place` and `reach` gain `looks` upstream (a valid edge: room is ... → looks → loops → place → reach →
  export). Every Look edit then makes `place`, `reach` and `export` stale, which is a deterministic rebuild. `reach` runs
  one more set of floods per Look with its own `solid` (the laneway's room takes 1.4–1.7 s). `place` goes to version 3, `reach`
  to version 3, and `export` to version 3 (each is at 2 since the Links, tickets 0265 to 0267).
- **`markers.json` schema 3.** Each Marker has `look`, a Look ID or `null`, always written out. `place` refuses a `look`
  that names no built Look (`marker.unknown_look`, error, with the undo), and a `look` on any other Marker type
  (`marker.look_type`, error). For each Look with its own `solid`, `place` also writes `looks/<look>/walkable.png` and
  `looks/<look>/clear.png`. A schema 2 file is refused, naming the rebuild.
- **`report.json` gets a `schema_version`, at 1.** It has none today, and its older form is refused, naming the rebuild.
  It gains `looks`: per Look with its own `solid`, its `markers`, `main`, `islands` and `areas`, as the room's are. Each of
  the room's islands and walkable areas gains `looks`, the Looks that reach it. `reach` also writes
  `looks/<look>/reachable.png`. Its new findings are:
  - `reach.island_under_look` (info): a room island some Look reaches.
  - `reach.look_island` (warning): ground that only a Look makes walkable, and that it doesn't reach.
  - `reach.look_cuts_off` (info): a room Spawn or Exit unreachable under a Look (a shut door may mean it).
  - `area.not_reached` drops to info when a Look reaches the area.

  A Look's own Markers aren't reach targets, as the room's lights, emitters and interactables aren't.
- **`looks.json` stays at schema 1.** `look.overlap` is a new `looks` Check, a warning. The added and cleared Masks are
  derived in `export`, which already reads `masks` and `looks`.
- **`room.json` schema 12** (11 is ticket 0267's `links`).
  - The room's `markers` hold only the room's own.
  - Each Look gains `markers` (as the room's entries), `navigation` (vertices, polygons and outlines, or `null` without
    its own `solid`), and `added` and `cleared` beside `solid`, each as a file and collision shapes.
  - `masks` gains `<look>.added` and `<look>.cleared` (`masks/<look>.added.png`, `masks/<look>.cleared.png`, 1-bit, the
    room's size).
  - `collision.solid` stays the room's whole `solid`, so another Exporter reads the data and not the scene's arrangement.
- **The scene.**
  - The room's `solid` body holds the room's `solid` minus every pixel some Look clears.
  - `LookSolids/<look>/added` is a body, disabled.
  - `LookSolids/<look>/cleared` is a body, enabled: the pixels that this Look alone clears.
  - Pixels that several Looks clear form one enabled body per set of Looks, carrying the Looks' IDs in
    `metadata/kiripix_looks`, so that it is off while any of them shows.
  - A Look's whole-Mask body goes; its PNG (`masks/<look>.solid.png`) stays for the game's grid.
  - `LookNavigation/<look>` is a `NavigationRegion2D` with `enabled = false`.
  - `LookMarkers/<look>` is a `Node2D` with `visible = false` and the Look's metadata. It holds the Look's Markers with
    the room's node types, a light `enabled = false`, each with `metadata/kiripix_look`.

  With no Look shown, the scene collides exactly as before.

  Simplified shapes can leave a seam of up to `tolerance` px where a cleared body meets the room's body. The game's grid,
  read from the PNGs, has no seam.
- **The Manifest.**
  - `ids.markers` lists only the room's own Markers.
  - A new `ids.look_markers` lists the Look Markers as `<look>/<marker>`. Moving an exported Marker into or out of a
    Look changes its node path, so it is refused (`export.id_frozen`), as a rename is.
  - **Manifest schema 3** (the Owner's change to the draft, which added the list without a bump as `looks`, `loops`,
    `states`, `links` and `emotions` were). A schema 2 Manifest is migrated on read by a pure `migrate_v2` (`ids` gains
    `look_markers`, empty), as `migrate_v1` does, and the next export of the Asset rewrites it once at schema 3. An older
    Kiripix refuses a schema 3 Manifest, and `manifest merge` names a newer side as such.
  - The list is left out of the file when empty, as `looks` and the others are, so the bump is the only change to the
    Manifest of an Asset without Look Markers.
  - `manifest merge` takes the union of the new list too.
  - `ids.looks` is unchanged and freezes the Look node names under `LookSolids`, `LookNavigation` and `LookMarkers`.
- **What the game does to show a Look:**
  - shows every node whose `kiripix_id` is the Look's (as today);
  - shows `LookMarkers/<look>` and enables its lights (emitters are the game's to start);
  - enables `LookSolids/<look>/added`, and disables every cleared body that lists the Look;
  - disables `Navigation` and enables `LookNavigation/<look>`, for a Look with one;
  - for its grid, takes `solid` = room ∧ ¬(the shown Looks' cleared) ∨ (the shown Looks' added), from the PNGs;
  - hides a Loop under the Look, by its own room data (ADR 0011);
  - decides the draw order where two shown Looks overlap.

  A Loop's `light` may name a Look's light, which is then dark until the Look shows.
- **The UI:** a walk test and a `reach` view with a chosen Look, and a Marker's `look` on `place`.
- **Still open:**
  - navigation and `reach` for two Looks that both change `solid` and show at once (the game must not rely on either;
    declared combinations, above, would answer it);
  - a Look's own `pit`;
  - Exits, Spawns, areas and Links per Look;
  - side view;
  - a soft edge with binary alpha (decision 8: no room needs one yet).
