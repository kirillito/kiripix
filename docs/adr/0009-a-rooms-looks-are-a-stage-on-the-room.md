# A room's other Looks are a Stage on the room

A painted room is one baked picture, so a door that opens or a lamp that goes out needs its other appearance painted
too. We call this a Look (glossary). We considered three places for it:

1. **A child Asset per Look** (Kind `look`, parent `room.x`). It would get its own lock and journal, but it would repeat
   `brief`, `fit` and `palette`, and its `fit` and `palette` would have to read another Asset's Grid transform, palette
   parameters and Layers. The stage graph has no inputs that cross Assets; only Project checks look across them. The
   Exporter would then merge two Assets into one scene, and an ID scheme for children would be new.
2. **A Layer with a Condition, in `layers`.** A Layer is a plane of the base picture: the Plate and the Layers recompose
   exactly to the fit image, and that is a Check. A Look isn't part of that picture, so it would break that invariant.
   And every Look edit would rebuild `palette` and everything below it.
3. **A `looks` Stage on the room, after `palette`.** It reads the room's Source, Grid transform, Layers and palette
   mapping as ordinary upstream inputs. So a Look shares them exactly, and a change to any of them makes it stale through
   the normal graph.

We chose 3: room: brief → source → fit → layers → masks → palette → **looks** → place → reach → export.

A Look's image comes from an edit: an image-model edit of the room's Source, or one painted by hand. The edit is a
Variant of that Look, never of the room, and the Look's `pick` records the hash of the Source it was made from. The
Stage fits the edit with the room's Grid transform, maps it with the room's palette parameters, and cuts it to a
region. The Condition that shows a Look is an opaque string to Kiripix: only the game knows what `circuit.hall:off`
means.

## Consequences

- `looks` sits after `palette` because it needs the mapped composite: it maps each edit the same way, measures drift
  against it, and splits the region by the Layers' alpha. It calls no Runner. A later click-to-segment region would key
  its pinned call on the edit at Source resolution, not on palette output, so ADR 0004 still holds: a palette tweak
  rebuilds Looks deterministically and never asks for a Runner again.
- Edits live in `src/looks/<look>/`, outside the `source` Stage's `src/*.png`, so a new edit never touches the room.
- Re-picking the room's Source invalidates every Look's pick (`needs-input`: the edit was made from another Source). A
  refit replays the Looks into `needs-review`, as a changed input does for clicks.
- A room with no Looks has a `looks` Stage that is `done` at once. Adding the Stage makes `export` stale for every
  room; that is a deterministic rebuild, and `room.json` goes to schema 3.
- Look data lives in `room.json`, not only in the Godot scene, so a second Exporter (Phaser or Tiled) reads the same
  thing.
- Looks share the room's journal and lock. That is fine for one Owner. Splitting them out later would be a migration.
