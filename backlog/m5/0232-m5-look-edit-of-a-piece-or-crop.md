---
status: todo
milestone: M5
agent: core-engineer
type: ticket
---

# M5: a Look's (or a Loop's) edit made on a piece or a crop of an extended room

Found at the M4 gate ([0142](../m4/0142-m4-gate.md), 2026-11-16). Milestone M5 is a placeholder: the Owner picks it.

## The gap

`import --look` takes an edit of the room's whole Source and registers it to it. An extended room's Source is the joined image
(the laneway's is 2407 x 1343). The Owner's image model (Nano Banana) resizes what it's given to its own size (1376 x 768
here), so an edit of the joined Source comes back smaller and has to be scaled up again: the Look is blurred. A Look can only be
made sharp from an edit of one unmerged piece (`extend/pieces/`, or the first Variant) or of a crop of the Source at the
model's size.

At the gate, the back gate's Look was made from an edit of the NW piece, pasted 1:1 into a copy of the Source by a scratch script
outside Kiripix, then imported. That works because the NW piece is the Source's top-left at scale 1; a piece the join scaled,
or a crop, needs Kiripix's registration.

## What to build

- `import <room> <png> --look <look> --of <piece|crop>`: the edit is of one of the room's pieces (its hash, as `extend`'s journal
  names it) or of a crop Kiripix wrote. Kiripix registers it to that piece's place in the Source (the join's `register` and the
  journal give it) and stores an edit of the whole Source, the rest of it the Source's own pixels, so `looks` is unchanged.
- **A crop to edit:** a way to write the Source's crop around a box at the image model's size (1376 x 768, or a size given), the
  way `extend canvas` writes a canvas, for a Look that no single piece holds whole.
- The same for a Loop's edit frames (`import --loop <loop> --frame <n>`).
- The region still decides what shows: an edit of a piece may redraw outside the Look (`look.drift`), as before.

## Acceptance criteria

- [ ] CLI seam: an edit of a scaled piece and an edit of a crop each give a Look whose pixels outside the edited area are the
      room's, and whose registration residual is under a target pixel.
- [ ] A crop is written at the asked size, and its edit comes back to the same place.
- [ ] Spec §6.1 (Looks) and the `import` help say which edits are accepted.
