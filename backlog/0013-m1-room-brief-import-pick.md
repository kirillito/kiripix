---
status: todo
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0011-m1-decision-journal.md]
---

# M1: room brief, `import` and `pick`

Spec §6.1 (brief, source) and §10.5. User stories 9, 10 and 22 of [0010](0010-m1-room-end-to-end.md).

## What to build

- The room's `brief` Stage runs: it writes the brief (size, view, mood) to its output, and reports
  `brief.size_not_tiles` when the width or height isn't a multiple of `project.tile`. Prompt rendering waits for
  `gen` (M4).
- `kiripix import <id> <file>`: copies an image into `src/` as a new Variant (named by its hash, so importing twice is
  a no-op), and refuses a file that isn't a PNG with a finding. Variants are immutable once picked.
- `kiripix pick <id> <variant>`: records the Pick Decision on `source` (the same entry `decide` would write).
- The `source` Stage runs: with a Pick it outputs the picked Variant as the Source; without one it is `needs-input`
  with "no Source picked"; with a Pick of a deleted Variant it is `needs-input` with that reason.
- `next` gives the exact command for these Stages: `kiripix set … width=… height=…` for a size problem,
  `kiripix import <id> <file>` with no Variant, and `kiripix pick <id> <variant>` (as an `owner_action` when there are
  several Variants to choose from).

## Acceptance criteria

- [ ] `new room …`, `set … brief width=480 height=272`, `import`, `pick`, `run` leaves `brief` and `source` `done`
      and `fit` next.
- [ ] A brief of 481 px with `tile = 16` reports `brief.size_not_tiles` with a `fix`.
- [ ] Importing a second Variant and picking it makes `source` and everything below it `stale`.
