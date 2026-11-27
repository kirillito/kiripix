---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0401-m6-import-a-pixelbolt-atlas.md]
---

# M6: `import --loop` reads a Pixelbolt atlas

Spec §6.1 (`loops`), ADR 0011 and §10.5. F3 of the trial [0402](0402-m6-pixelbolt-room-loops-trial.md), filed by the Owner on
2026-11-27 for the next rooms. [0401](0401-m6-import-a-pixelbolt-atlas.md) reads a Pixelbolt atlas into a `sprite`; this ticket
reads one into a room's frame Loop, with the same reader (`kiripix/core/atlas.py`).

## The gap

In 0402, each Pixelbolt Loop took a script: `loop kit` with N + 1 frames, Pixelbolt's frame k copied to kit frame k + 1,
`import --loop` of frames 1 to N, then a `timing` Decision typed by hand with `ticks` (ms x 60 / 1000, rounded) and `rest: true`,
because frame 0 is the room and Pixelbolt's frame 0 is a motion frame. Every number is in the atlas, and a typo shifts the timing
without a finding. The trial found that a Pixelbolt frame with transparent pixels imports as it is: the room shows through.

## What to build

- `kiripix import <room> <file.atlas.json> --loop <loop> [--animation <name>]` (or a folder holding one `*.atlas.json`), on a frame
  Loop that has a region. Kiripix recognises the atlas as 0401 does (`meta.app == "Pixelbolt"`, `meta.image` beside it, the
  `import.atlas_version` info, the refusals `import.atlas_image_missing`, `import.atlas_rotated`, `import.atlas_rect`, trimmed
  frames placed by `spriteSourceSize` in `sourceSize`).
- **Which animation:** `--animation` names it; without it, the atlas's only animation. Several and none named is
  `import.atlas_ambiguous` (refused, naming them).
- **Frames:** the animation's frames, in its expanded order, become the Loop's frames 1 to N; frame 0 stays the room. A frame
  listed twice (a pingpong) is stored once and played twice, if the Loop's `timing` can say so; if it can't, find what it can say
  (`ticks`, `pingpong`) and map onto it exactly, or refuse with a finding naming the order.
- **Size:** each cell must be the Loop's box size (the size `loop kit` writes); otherwise `import.atlas_size` (refused, naming
  both sizes). The usual kit checks then apply (off-palette, alpha 0 or 255, strokes outside the region cut), as for a kit.
- **Timing:** a `timing` Decision with `ticks` from each frame's `duration` (floor(ms x 60 / 1000 + 0.5), at least 1, as 0401
  rounds), `rest: true`, and `import.ticks_rounded` (info) when the rounding moves the total by more than one tick. An atlas
  animation with `loop: false` imports with `import.atlas_one_shot` (warning): a Loop always loops.
- **One step:** the frames and the `timing` Decision are one import, and one `undo` returns the Loop to its frames and timing
  before (0401 made a re-import one step by recording one Decision; use the same idea or the journal's own way, without a journal
  format change if one isn't needed). A refusal changes nothing; everything is checked before the first write.
- **Kept beside the kit:** the atlas, its PNG and the recipe (`*.pixel.json`, `*.fx.json`) are stored with the Loop's kit files
  in `src/`, as a note; nothing reads the recipe.
- The plain `import --loop` of kit PNGs and `--loop --frame` edits work exactly as before.
- Spec §6.1's `loops` row and §10.5's `import` line say so.

## Acceptance criteria

- [ ] CLI seam: a fixture atlas (made for the test, a few pixels, the Loop's box size, 3 frames of 50 and 70 ms with
      transparent pixels) imports into a room's frame Loop; `run`, `check` and `export` build; `room.json`'s Loop has the frames,
      the `sequence` with the rounded ticks and `rest`, and frame 0 is the room.
- [ ] CLI seam: a pingpong animation plays its repeated frame twice, or is refused with its finding, as built.
- [ ] CLI seam: each refusal (wrong size, several animations with none named, and 0401's atlas refusals) changes nothing.
- [ ] CLI seam: a re-import is undone by one `undo`; a plain kit import and an edit frame import exactly as before.
- [ ] `lint-imports` and `mypy` pass.
