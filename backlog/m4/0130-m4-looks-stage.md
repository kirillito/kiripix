---
status: todo
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0127-m4-room-looks.md
---

# M4: the `looks` Stage

Spec §6.1 (the `looks` row and Looks); ADR 0009. After [0128](0128-m4-room-look-edit-trial.md)'s numbers, and with
[0129](0129-m4-look-variants.md)'s Variants.

## What to build

- **Decisions,** each naming its Look: `look` (ID, Condition); region `polygon`, `brush` and `difference` (box,
  tolerance, specks removed; on the image); `solid` by polygon or brush. The `masks` Stage's `snap_cell` applies to
  `solid`.
- **The build,** per Look: resize to the Source, register (`register`), fit through the room's Grid transform, regrade
  (`regrade`: `none` or `outside`), map the whole image with the `palette` Stage's parameters and Ops, then cut the region.
  Write the Look's image cropped to the region's box, one piece per foreground Layer the region meets (the pixels in
  that Layer's alpha), and its `solid`. If [0094](../0094-m3-palette-stage-muddies-rooms.md) changes the mapping, Looks
  follow it, because they call the same code.
- **Replay:** a refit or a Layer change sends `difference` regions and registration to `needs-review`; a palette change
  rebuilds them to `done`. No Looks, `done`.
- **Checks:** `look.off_palette`, `look.misaligned` (error), `look.drift` (warning, count and boxes), `look.unchanged`
  (warning). Each finding has a `fix` or an `owner_action`.
- **Ops** for registration (scale and shift, estimated outside a Mask), regrade and the difference region, in `ops/`,
  pure, with golden tests.
- Calls no Runner.

## Acceptance criteria

- [ ] Golden: registration recovers a known 1 % scale and a 3 px shift; a difference region picks out a changed patch
      and not the noise around it.
- [ ] CLI seam, with the `demo` Kind or a small room: a Look over a lifted Layer gives a Plate-depth image and a piece for
      that Layer whose pixels together equal the mapped edit inside the region.
- [ ] An edit with drift outside the region gives `look.drift` with its box; one shifted beyond the limits fails with
      `look.misaligned`.
- [ ] A palette change rebuilds the Looks to `done`; a refit with a `difference` region gives `needs-review`.
- [ ] Contract samples for the new Decisions.
