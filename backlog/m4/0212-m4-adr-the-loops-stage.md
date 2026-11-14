---
status: todo
milestone: M4
agent: reviewer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0189-m4-loops-stage.md, 0190-m4-export-loops.md, 0195-m4-export-layer-loops.md]
---

# M4: ADR 0011: a room's Loops are a Stage beside its Looks

0183 planned this ADR "with 0189", and it wasn't written ([0189](0189-m4-loops-stage.md), Result). The format is in
`docs/adr/`, beside [ADR 0009](../../docs/adr/0009-a-rooms-looks-are-a-stage-on-the-room.md).

## What it records

- `loops` is a Stage of its own after `looks`, not an animated Look (0183's Decision 5). It shares the region Decisions and
  the edit pipeline through `recipes/regions.py`.
- Frame 0 is always the room. Cycles are baked into frames, and the game has one player stepping a `sequence` of whole
  ticks.
- A Loop's `light` is a plain light Marker ID. `loop.light_unknown` is an `export` Check, because the Markers come from
  `place`, which runs after `loops`. So `export` reads `loops` upstream.
- Looks and Loops share one ID set. The `loops` Stage enforces it, which is enough because `export` can't run past a clash.
  The Manifest freezes each list on its own and doesn't enforce the set.
- The latest `loop`, `cycle` and `timing` Decision replaces the whole one before it, as a `marker` Decision does.
- A Loop on a Layer: whole-Layer frame Loops take the Layer's own sprite (`moves_layer`), and others are child pieces over a
  remainder (0211).
- Still open: a pulse on a ramp's light end doesn't move; the flash area is measured against `project.resolution`;
  `flicker` has no seam measure.

## Acceptance criteria

- [ ] `docs/adr/0011-...md` in the ADR format. It cites 0183's Decisions, and the spec's §6.1 and §9 match it.

Budget: 30–60k tokens.
