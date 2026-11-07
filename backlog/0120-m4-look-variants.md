---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0118-m4-room-looks.md
---

# M4: a Look's edit Variants: `import --look` and `pick --look`

Spec §4, §6.1 (Looks) and §10.5; ADR 0009.

## What to build

- `kiripix import <id> <png> --look <look>` stores an edit Variant under `src/looks/<look>/<hash>.png`. That is outside
  `source`'s `src/*.png`, so the room's `source` Stage stays `done`. JPEG converts to PNG, as `import` does now. Refused on a
  non-room Asset and on a room with no picked Source.
- `kiripix pick <id> <variant> --look <look>` records a `pick` Decision in the `looks` journal, with the room Source's
  hash at that moment. One Variant needs no judgement, so an agent may pick it, as for a room's Source.
- The `looks` Stage's inputs include `src/looks/**`, so a new edit makes `looks` stale and nothing above it.
- A pick whose Source hash isn't the current Source's doesn't apply: `needs-input` with the reason "the edit was made
  on another Source", and an `owner_action` to re-make it.
- `describe room` lists the new options.

Coordinate with [0121](0121-m4-looks-stage.md), which declares the Stage. This ticket can land first, with the Stage
declared and a build that does nothing.

## Acceptance criteria

- [ ] At the CLI seam: `import --look` adds a Variant, and `status` shows `source` still `done` and `looks` stale.
- [ ] Re-picking the room's Source puts `looks` in `needs-input` with that reason.
- [ ] Samples in `tests/cli/test_contract.py` for the changed inputs.
