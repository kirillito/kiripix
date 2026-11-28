---
status: todo
milestone: M7
type: spec
---

# M7: The `tileset` Kind: a tile kit for the game's procedural dungeon

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6 (Kinds), §14 ("The tileset recipe, estimated on 2026-11-08", and
trial [0251](../m5/0251-m5-tileset-trial.md)). The game's side: DEC-078 and its S1 track (`../urban-mystery-club/docs/backlog/s1/`,
0202–0207). Not split into tickets yet; the milestone is the Owner's call.

## Why now (the Owner, 2026-11-25)

- **The game has a procedural dungeon.** S1, the PATH: a seeded combat dungeon of corridors, junctions and halls on a
  **modular tile kit** (DEC-078, which settles ISS-017 for the PATH only; Lower Bay and the regular dungeons keep painted
  rooms until the game's M13 test). The game builds it with grey-box placeholder tiles now; "the real tile kit (PATH tiles,
  shopfronts with fictional names, signage, food courts) via Kiripix" is on its list for later.
- **The art is assumed possible.** 0251 found the free image model wouldn't lay out a kit and baked light into every piece.
  With GPT Image (0379) the Owner's working assumption is that a usable sheet can be painted; a trial of that is a separate
  ticket, not this one. The recipe should still not depend on one perfect sheet (see "Source" below).

## The split

- **The game owns** the generator (s1/0203: a seeded `PathFloor` in `core/`), the builder that turns a floor into a room
  (s1/0204), encounters and the visit. Kiripix holds no layout or game rules.
- **Kiripix owns** the tile kit: the tiles as pixel art in the Project's palette, what each tile is, how tiles join, their
  collision, and the export the game's builder reads. It also exports the PATH's set dressing (shopfronts, signs, benches)
  through the existing prop recipe, with states.

## What the export has to fit

The game's builder (s1/0204) doesn't use Godot's `TileMap`: it **draws the tiles into one `Plate` image** per floor and makes
collision from wall cells, so a generated floor looks to `Room` like an exported Kiripix room. Its grey-box kit is 16 px:
flat floor, wall top, wall face, a pillar. And m13/0161 (Lower Bay's construction test) is to reuse that builder with real
tiles on hand-authored layouts. So:

- **Decide in an ADR** whether `export` writes (a) an atlas PNG and a kit file (JSON, `schema_version`) the game's builder
  reads, (b) a Godot `TileSet` `.tres` with terrains and physics as 2026-11-08's estimate said, or both. (a) fits the builder
  as planned; (b) only matters if the game moves to `TileMapLayer`. Recommendation: (a) now, (b) when the game asks.
- The kit file names each tile's **role** (floor, wall top, wall face, corner pieces, pillar, ...), its **edges** (which
  neighbours it joins: the terrain's peering bits), its **variants with weights** (so a long corridor doesn't repeat one
  tile), its **collision** (solid, none, or a polygon in tile px) and free **custom data** (e.g. `spawn_ok`, `light`).

## What to build (to be split)

- **Kind `tileset`:** brief → source → fit → palette → tiles → terrain → export, as estimated, plus:
- **Source** from GPT Image through `gen` (adding `tileset` to `GEN_KINDS`), or imported. Because a model may still not lay
  out a clean kit, `tiles` should also accept **swatches**: a floor or wall-face texture made seamless (wrap-offset and fix
  the seams, inpainting with the LaMa Runner), and wall strips cut from a painted image with their baked light evened out.
- **3/4-view walls at the 30° camera:** a wall's face is several tiles tall above its footprint. The terrain rules have to
  cover a wall top, its face and their corners (inner and outer), which is the hardest part of this projection. Settle the
  terrain mode in the ADR (a 16-tile corner set, or the 47-tile blob set).
- **Checks:** `tileset.incomplete` (every neighbour combination the terrain mode needs has a tile, since a generator reaches
  every one); `tileset.seam` (edge match between tiles that join); `tileset.palette` (the Project's palette); light even
  across a tile and its neighbours.
- **A preview** that lays out a throwaway sample floor from the kit (corridors, a junction, a hall, every corner), so the
  Owner sees the seams without opening Godot. Preview only: not the game's generator.
- **UI:** the kit's sheet with each tile's role and edges, the terrain Decision in a keyboard flow, the sample floor.

## Open questions for the Owner

1. The milestone: after the M6 gate, or as a side track beside it (like the game's S1)?
2. Export (a), (b) or both (above).
3. Does Lower Bay's construction test (the game's m13/0161) use this kit too, or only the PATH?

## Estimate

2026-11-08's 8–10 tickets and 2–3.5M tokens, toward the top: the 3/4 walls, the completeness Check and the swatch route
add to it, and the kit file's ADR and its migration add one ticket.
