---
status: done
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

- [x] `docs/adr/0011-...md` in the ADR format. It cites 0183's Decisions, and the spec's §6.1 and §9 match it.

Budget: 30–60k tokens.

## Result (2026-11-14)

- `docs/adr/0011-a-rooms-loops-are-a-stage-beside-its-looks.md`, in ADR 0009's format. It cites 0183's Decisions 2, 5, 6, 8
  and 9, and records the code as of 0206, 0207, 0211, 0222 and 0223: a held Loop holds only itself (`loop.held`,
  `export.loop_held`) and the adviser hook `register_adviser`; `remove` and `rename` through `decisions_view`; `lift` in
  OKLab L; `timing.rest`. Edit frames (0219, 0220) are named only as in progress.
- **The Layer rule as built (0211), not as the ticket worded it:** a Layer's own `Sprite2D` takes a Loop's strip only when
  that frame Loop covers every opaque pixel of the Layer and is the only frame Loop with a piece on it. Otherwise the Layer
  shows its remainder and every strip is a child. It isn't "the first by ID".
- **The ID set:** besides the `loops` Stage's hold, `decide` now refuses a `rename` onto a taken ID (`loop.id_taken`, 0207),
  and the adviser gives only the Look's way out when the Loop is already exported (0206). The Manifest still doesn't enforce
  the set.
- Spec §6.1 (the `loops` and `export` rows, the end of Looks) and §9 (Loops in the Room row, the Manifest's contents and
  Frozen IDs) were brought in line with the ADR, plus the line in "Changes since v0.4". §9 had no Loops text before this.
- **Still open, re-checked against the code:**
  - A pulse on a ramp's light end still doesn't move under `lift`. `cycle_pulse` searches only from the pixel's own place
    to the ramp's end, so a pixel at the end keeps its colour. `loop.still` fires only when no pixel of the Loop moves.
  - The flash area is still measured against `project.resolution` (`_screen_area`).
  - `flicker` still has no seam measure (the ratio is fixed at 1.0).
- **Found while drafting, for later tickets:**
  - With `rest`, the game should set `frame` to the first played frame on its first tick (0222, the game's backlog).
  - Under `rest`, the held reason for a wrong-length `ticks` list still says "one number per frame" (0222).
  - The ID clash in `loops` takes every ID named in a `looks` Decision, but `loop.id_taken`, the adviser and the freeze take
    only picked Looks. A Loop renamed onto a declared, unpicked Look passes `decide` and is then held.
  - Stale wording in `kiripix/recipes/room.py`: the `loops` StageSpec's description says "Here a Loop is a colour cycle",
    and `_loop_source`'s docstring says "`edit` ... is held until trial 0184". The `frames` Decision's value is `edits`, so
    `room.json`'s `source` will read `edits` once 0220 builds them.
  - A Layer whose `Sprite2D` takes a Loop's strip also takes the Loop's unshaded material, unlike the other Layers. The
    Owner should check that against how the game lights Layers.
  - Refusing `remove`/`rename` of an exported Loop exits 1; a Layer's `remove` exits 2 for the same finding (left by 0207).
  - "Remainder" isn't in the glossary.
  - §10.5 has no `loop kit` line, and its `import` line doesn't show the kit form (`--loop l [--kit kit.json]`).
