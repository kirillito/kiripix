---
status: done
milestone: M1
agent: imaging-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0015-m1-fit-and-layers-pass-through.md]
---

# M1: the palette Stage

Spec §6.1 (palette) and §7 (colour, cleanup). User story 16 of [0010](0010-m1-room-end-to-end.md).

## What to build

- Op (`cleanup`): orphan pixel removal (islands up to `orphan_size` pixels take their most common neighbour colour).
  Pure, golden-tested.
- The room's `palette` Stage maps the Plate (in M1, the whole room) with the M0 quantise Op, with `dither` and
  `strength` as parameters, then removes orphans. Its upstream is `layers`, so a Mask edit doesn't rebuild it.
- Checks: `palette.off_palette` on the output; `layers.recompose_mismatch` passes trivially with no foreground Layers.
- Changing `style/palette.gpl` makes `palette` and everything below it `stale`.

## Acceptance criteria

- [x] Golden tests for orphan removal at sizes 0, 1 and 4.
- [x] A fit room runs through `palette` with every pixel on the palette, and `check` reports nothing.
- [x] A `decide` on `masks` leaves `palette` `done`.
