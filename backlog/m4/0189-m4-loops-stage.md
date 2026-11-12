---
status: todo
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0184-m4-ambient-animation-trial.md, 0188-m4-cycle-ops.md, 0130-m4-looks-stage.md]
---

# M4: the `loops` Stage, with colour cycles

Part of [0183](0183-m4-ambient-animation.md), route (b). Spec §6.1 (Looks, whose code this shares) and the glossary (Loop).
This ticket builds the Stage that frame loops (0192, 0194) extend, so it carries the skeleton.
**Defaults marked "set by 0184" come from the trial.**

## What to build

- **The Stage:** `loops` in the room Recipe after `looks` and before `place`. It reads `palette`'s output, `layers`' Plate and
  Layers, and the Looks' regions (for one Check). With no Loops it is `done`. `place` and `reach` don't read it. The spec's
  §6.1 table and Recipe line get the Stage.
- **Shared code:** move the edit pipeline (resize, register, fit, regrade, map, cut, split by Layer) and the region Decisions
  (`polygon`, `brush`, `difference`) out of the `looks` Stage into one module in `recipes`. `looks` uses it unchanged, and its
  tests pass unchanged.
- **Decisions,** in target px, each naming its Loop:
  - `loop`: ID (the Marker ID rule, unique among Looks and Loops), `form` (`cycle` here; `frames` is accepted and finds
    `needs-input` until 0192), `layer` (`plate`, the default, or a foreground Layer's ID), `light` (optional, a light Marker ID),
    `phase` (ticks, default 0).
  - region: `polygon`, `brush`, `difference` (shared), and `flood`: the colour region within an OKLab tolerance of a clicked
    pixel, as on `masks` (default tolerance set by 0184).
  - `cycle`: `colours` (hex, in order, each on the palette) and `mode` `rotate` or `pulse` (with `depth` and `steps`), and for
    `pulse` an `emissive` flag (default true).
  - `timing`: `ticks` (one number or a list per frame), `pingpong`, or `flicker` (`seed`, `mean_ticks`, `spread`,
    `length_ticks`), expanded into a sequence at build time by 0188's Ops.
- **Output** in the Stage's folder: per Loop, the distinct frames as one strip PNG (side by side, wrapping into rows past
  4096 px), a piece strip per foreground Layer the region meets (cut by the Layer's alpha), the index PNG for a cycle, and
  `loops.json` (ID, form, layer, box, files, frame count, `sequence`, phase, light, colours, mode). A Loop on a Layer
  (`layer = <id>`) is cut to that Layer's alpha here; frames that move past it come in 0194.
- **Checks:** `loop.off_palette` (error), `loop.frame0` (error), `loop.seam` (warning, `seam_ratio` over 3.0, set by 0184; its
  `fix` sets `pingpong`), `loop.still` (warning), `loop.flash` (**error**, decided by the Owner; its `fix` sets a slower
  `timing`), `loop.overlaps_look` (warning), `loop.pulse_spills` (info: a `pulse` region that reaches more than 2 px, set by
  0184, beyond the pixels of its picked colours), `loop.light_unknown` (error: `light` names no light Marker),
  `loop.texture` (info: frames and bytes for the room).
- **Staleness:** a palette change rebuilds cycles (`done`); a refit or a Layer change puts `difference` and `flood` regions in
  `needs-review`. Loop IDs freeze on export, like Look IDs (the Manifest's ID list gains `loops`).
- `describe room --stage loops`: the schema, and text that says a Loop always plays and a Look is shown by game state, and
  that a character clip's `loop` flag is something else (decided by the Owner, 2026-11-12).

## Acceptance criteria

- [ ] CLI seam on the `demo` test Kind or a test room: a `rotate` and a `pulse` Loop, a `flicker` timing, a Loop over a
      foreground Layer giving a piece; each finding above; `undo` of a region.
- [ ] CLI seam: `looks`' existing tests pass unchanged after the move to the shared module.
- [ ] CLI seam: frame 0 of every strip equals the room inside its region, pixel for pixel; a palette change rebuilds and stays
      `done`.
- [ ] The contract sample passes; `lint-imports` and `mypy` pass.

Budget: 250–350k tokens.
