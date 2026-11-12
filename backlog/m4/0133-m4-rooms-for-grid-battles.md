---
status: todo
milestone: M4
type: spec
---

# M4: rooms for grid battles

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6.1, §9, §14 (M4) and §16 (open decisions 7 and 8); [the glossary](../../GLOSSARY.md)
(Marker, Area, Mask, Look). The game's design change is in `../urban-mystery-club/docs/DECISION_LOG.md` (DEC-048, ISS-022) and
`docs/TECHNICAL.md` §4.5 and §6.

## Problem Statement

On 2026-11-08 the game moved combat to tactical turns on a grid (DEC-048). A fight still happens in the painted room: a battle
area in the room becomes a grid of 32 px cells (2 x 2 tiles, to confirm in the game's M05), built from the `solid` Mask. Up to five
club members and their enemies deploy on it, so rooms grow, often larger than one screen in both directions. Boss phases change
the room mid-fight.

Kiripix can't say where a battle area is. It gives the game its Masks only as simplified collision polygons, which are lossy at a
cell's edge. Large rooms are joined by hand, and no room has been extended in both directions yet.

## Solution

The Owner decided on 2026-11-08 that M4 is about current issues and preparing rooms for combat. Generation, agents and side view move
to later milestones (M5 and M6; since 2026-11-11, generation is M6 and side view is under Later).

- **Large rooms:** a trial of a room extended in both directions and taken to export. Then the join tool, without a Provider:
  Kiripix writes the canvas for the next piece, and joins the piece the Owner made in the image model's own UI.
- **An `area` Marker:** a box with a stable ID, optionally snapped to a cell, exported as an `Area2D`. Kiripix gives it no meaning.
  The game reads `battle.*` IDs as battle areas, and keeps its own rules (minimum size, connected cells, deployment) in its
  content check. Deploy cells live in the game's encounter data, so no new point Marker is needed. A room holds any number of
  areas with any ID, one cell wide at least. Not every area is for standing in: the laneway's `escape.*` area over the fence,
  an Exit's trigger box (spec §6.1) or a camera frame has no walkable pixel, so the walkable Checks apply only to an area
  marked `walkable` ([0137](0137-m4-area-marker.md); decided by the Owner, 2026-11-12).
- **The Masks reach the game as images,** with `room.json`, so the game builds cells from exact pixels.
- **Room Looks without generation** ([0127](0127-m4-room-looks.md)): imported edits with their own `solid`, for boss phases
  (lights fail) and doors. A moving bench is a Prop that the game moves, not a Look (the Owner, 2026-11-08), so open decision 8
  stays open. The game binds each Look by its ID in its own room data, so a Look's Condition is an optional label
  ([0131](0131-m4-looks-export.md)).
- **The game's M05 bins, decided by the Owner on 2026-11-12:** the boss knocks the bins over mid-fight. The game's plan asks for
  "a Look with its own `solid` (fallback: props)", but a toppled bin frees the cells it stood on, which is a Look taking
  collision away (open decision 8), and bins are per-cell cover, which the game keeps on its grid anyway. So the same rule as
  the bench: bins are Props (the prop recipe, M2) that the game places and moves, and the laneway is painted without them.
- **SAM 2 on large rooms,** only if the trial shows clicks get worse.

## Order

| Wave | Tickets |
|---|---|
| 0 | [0134](0134-m4-trial-room-extended-both-ways.md), the trial. It needs no code, so it may run during M3. |
| 1 | [0137](0137-m4-area-marker.md), then [0138](0138-m4-export-area.md) and [0139](0139-m4-ui-draw-an-area.md) |
| 2 | [0140](0140-m4-export-masks-and-room-json.md) |
| 3 | [0135](0135-m4-join-ops.md), then [0136](0136-m4-extend-commands.md) |
| 4 | Looks: [0128](0128-m4-room-look-edit-trial.md), [0129](0129-m4-look-variants.md), [0130](0130-m4-looks-stage.md), [0131](0131-m4-looks-export.md), [0132](0132-m4-ui-looks-screen.md) |
| 5 | The SAM 2 crop, if 0134 shows clicks get worse on a large room; 0134 files that ticket |
| 6 | [0141](0141-m4-agent-acceptance-test.md), then the gate [0142](0142-m4-gate.md) |

**Looks stay in M4** (the Owner, 2026-11-12), though with the bins as Props no game milestone before its M09 (R6: the power
comes back and the lights come on) uses a Look. So wave 4 doesn't block the game's M04 or M05, and may run after wave 5 if
another wave needs the agents first.

**Don't run these at the same time, because they edit the same files:**
- 0137 and 0130 (`kiripix/recipes/room.py`).
- 0138, 0140 and 0131 (`kiripix/export/`). Each one bumps `room.json`'s `schema_version`, so they take turns.
- 0139 and 0132 (`web/src/`).

## User Stories

1. As the Owner, I want to mark where a battle can happen in a room, with an ID the game can find, so that an encounter claims it.
2. As the Owner, I want an area's edges on the battle grid, and to see which cells my Mask leaves half-blocked, so that every
   cell is clearly open or blocked.
3. As the game, I want the `solid` and `pit` Masks as exact images, so that the battle grid matches the collision.
4. As the Owner, I want Kiripix to write the canvas for the next piece of a room and join the piece I bring back, so that a
   room two screens wide and tall doesn't cost me an hour of manual joins.
5. As an agent, I want the same through the CLI, so that I can prepare and join pieces for the Owner.
6. As the Owner, I want a boss phase's changed look (lights out) as a Look with its own `solid`, so that the game switches it
   mid-fight.
7. As the game, I want an area that isn't for standing in (an escape route over a fence, an Exit's trigger box) without a
   walkable error, so that every rectangle the room's play needs is drawn on the room.

## Out of scope

- Game rules: minimum battle-area size, connected cells, deployment space. They belong in the game's content check.
- Polygon areas. A box is enough for M05; a polygon comes when a room needs one.
- A lighter collision export. The Owner expects normal rooms to have far fewer pieces than `harbor_front` (an anomaly from
  the old brush tool). 0134 counts them on a full room, and a ticket follows only if the count is high.
- Providers, `gen`, MCP and image-to-3D (M6); side view (Later). Palette ramps per part are in M4 ([0147](0147-m4-character-palette-ramps.md)).
