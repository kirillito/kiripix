---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: `palette-suggest` from a room, or a box of it

Spec §7 (palette suggestion). Found on the laneway ([0134](../m4/0134-m4-trial-room-extended-both-ways.md), "The palette's
warm light"): a sun patch banded, and the fix was `palette-suggest` on a crop cut by hand into
`.kiripix/trials/laneway_light_patch.png`, at a scale guessed from the default.

## The gap

`kiripix op palette-suggest <image>` takes an image file and a `--scale`. For a room, the right input is the room's own
Source at its own Grid transform, and often only the part that bands.

## What to build

- `palette-suggest --asset <room> [--box x,y,w,h]`: reads the room's Source and its `fit` Grid transform (so `--scale` is the
  room's, not the default), with the box in target pixels mapped through the transform. Without `--box`, the whole room.
- It writes the proposal as now (`proposal.json` names the Asset and the box it was made from, so `palette-add` can tell it's
  current).
- An image path still works as today.
- `palette.mapping_error` findings (or whichever finding reports banding) offer this Command, with the region's box, as their
  `fix`, where they have one.

## Acceptance criteria

- [x] CLI seam: on a built fixture room, `--asset` with a box gives the same proposal as the old path on a crop of the Source
      at the room's scale.
- [x] A room whose `fit` isn't built is refused, with `run <room> fit` as its fix.
- [x] The Command's help and spec §7 say so.

## Result

- `op palette-suggest --asset <room|prop> [--box x,y,w,h] --add N` reads the Asset's Source, cuts the box (target px) to
  Source px through the `fit` Grid transform, and downscales it by that crop's size, so the scale is the room's. `--scale`
  is ignored there. `data` has `box`; `proposal.json` has optional `asset` and `box` (still schema 1: both default to null),
  and `palette-add`'s stale-proposal fix re-runs the `--asset` form.
- `fit` not built: `palette.suggest_needs_fit`, fix `kiripix run <room> fit`. A bad box: `palette.box_invalid`. An image
  with `--asset` or `--box` without it: `palette.suggest_input`.
- `palette.mapping_error` on a room or prop now offers `op palette-suggest --asset <id> --add 16` (the whole Asset; the
  Check has no region box).

Tests: `tests/cli/test_palette_grow.py` (two new); `test_contract.py` unchanged (the Command's sample still runs). Spec section 10 CLI list updated.

Review fixes:
- An `--asset` proposal's `image_hash` is a hash of the Source and the `fit` `grid.json`; `palette-add` recomputes it and
  refuses a changed one with `palette.proposal_stale`, fix the `--asset ... --box ...` re-run (the box is kept, also in the
  fix for an unreadable proposal).
- `--asset` on a Kind other than room or prop: `palette.suggest_input`. A malformed box (wrong count, not integers):
  `palette.box_invalid`; so is a box whose cells reach past the Source (no test: a Grid reaching past its Source isn't
  built by `fit`).
- `check_mapping` decides by the Asset's Kind (`StageRun.kind`, set by core), and a Prop's other state (its `fit` under `states/<id>/`) gets the
  image-path fix, not `--asset`.
- The spec line moved to section 7; section 10 keeps a pointer.
- Tests: two more in `tests/cli/test_palette_grow.py`.
