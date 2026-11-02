---
status: todo
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0013-m1-room-brief-import-pick.md]
---

# M1: `check` and `preview`

Spec §10.2 and §10.5. User stories 20 and 21 of [0010](0010-m1-room-end-to-end.md).

## What to build

- `kiripix check <id>` runs every Check of every Stage that has an output, and lists the findings with positions
  (Asset, Stage, file, x/y). Exit code 2 on any error-severity finding. A Probe: it records nothing and takes no lock.
- `kiripix check --all` runs every Asset, plus the Project checks registered so far. The Project check hook is part of
  this ticket; Exit pairing arrives in [0022](0022-m1-export-ownership-and-id-freeze.md).
- `kiripix preview <id> [--stage s] [--overlay masks]` writes a PNG to `.kiripix/previews/` at an integer zoom and
  prints its path; without `--stage` it previews the last `done` Stage. `--overlay masks` tints each Mask over the
  image (the overlay Op is pure, in `ops`); it is exercised once Masks exist, in [0016](0016-m1-masks.md).
- Both get contract-test samples.

## Acceptance criteria

- [ ] `check` on a room with a bad brief exits 2 and lists `brief.size_not_tiles` with a `fix`; on a clean room it
      exits 0 with no findings.
- [ ] `preview` of `source` writes a PNG whose size is the Source's size times the zoom.
