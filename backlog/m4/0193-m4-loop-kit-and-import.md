---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0184-m4-ambient-animation-trial.md, 0189-m4-loops-stage.md, 0129-m4-look-variants.md]
---

# M4: the loop kit, and importing frames

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §10 (Commands) and §6.1 (Looks: `import --look`, `pick --look`).
Two Owner-made frame sources: a kit painted by hand at target size, and image-model edits of the Source. 0194 builds them.

**Part B (edit frames) is the most cuttable work in 0183.** If the trial (0184) finds that edit frames flicker too much to
use, cut Part B and say so in 0183.

## Part A: the kit

- `kiripix loop kit <id> <loop> <folder> --frames N`: writes `frame_000.png` (the region's box at target size, from the room
  after `palette`, alpha 0 outside the region), copies `frame_001.png` … `frame_<N−1>.png` to paint on, `palette.gpl`,
  `palette.png` (a swatch strip) and a `README.txt` of three lines (paint on copies, stay in the box, use only the palette).
  It refuses a folder that already has frames unless `--force`. Not owner-only: an agent may prepare a kit.
- `kiripix import <id> <png…> --loop <loop>`: reads frames 1 … N−1 in name order (frame 0 is always the room's and is never
  imported; a `frame_000.png` among them is skipped with an info finding). Each must be the box's size exactly
  (`import.size_mismatch` otherwise). It records the hashes of the frames, the fit and the palette they were painted on.
- Staleness: a refit puts kit frames in `needs-input` ("painted on another fit"); a palette change keeps them and 0194 remaps
  them (`needs-review`).

## Part B: edit frames

- `kiripix import <id> <png> --loop <loop> --frame <n>`: adds a Variant of that frame, as `import --look` adds one of a Look.
- `kiripix pick <id> <variant> --loop <loop> --frame <n>`: chooses it, recording the hash of the room's Source. A new Source
  puts every edit frame in `needs-input` ("made on another Source").

## Both

- `describe`, the Commands' schemas and their contract samples; `next` suggests `loop kit` for a `frames` Loop with no source.

## Acceptance criteria

- [ ] CLI seam: `loop kit` writes the files above; frame 0 equals the room in the box; a second run without `--force` is refused.
- [ ] CLI seam: importing painted frames records them; a wrong size is refused; a refit puts them in `needs-input`.
- [ ] CLI seam (Part B): two edit frames imported and picked; a new Source puts them in `needs-input`.
- [ ] Contract samples for `loop kit` and the new flags pass.

Budget: 150–250k tokens (Part A alone: 90–150k).
