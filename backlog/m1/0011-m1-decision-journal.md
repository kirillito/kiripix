---
status: done
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: []
---

# M1: `set`, `decide`, `undo`, `redo` and the Decision journal

Spec §5 (the Decision journal) and §10.5. User stories 1–4 of [0010](0010-m1-room-end-to-end.md).

## What to build

- `kiripix set <id> <stage> key=value...`: validates each value against the Stage's parameters in `describe`, writes
  `[stages.<stage>]` in `asset.toml` atomically, under the Asset lock.
- `kiripix decide <id> <stage> --decision '<json>' | --file d.json`: validates the Decision against the Stage's
  Decision schema and appends a journal entry (ULID `id`, `parent`, Decision name, data) to
  `decisions/<stage>.jsonl`, LF, one object per line.
- `kiripix undo <id> <stage>` and `kiripix redo <id> <stage>` append `{undo: <id>}` and `{redo: <id>}` entries.
  Nothing is ever removed or rewritten.
- The Stage's current Decisions (the journal replayed in ULID order) become part of its input hash and are handed to
  its run function. Entries have room to record the hash of the image a click or Override was made on (used by
  [0012](0012-m1-override-accept-review.md)).
- Two entries with the same parent put the Stage in `needs-review` with the reason "divergent Decisions".
- `init` already writes `merge=union` for the journals; check that it covers `decisions/*.jsonl`.
- The `demo` Kind gains a Stage that accepts a Decision and writes its current Decisions to its output, for the tests.
- Each new Command gets a sample in the contract test.

## Acceptance criteria

- [ ] `set` with an unknown key or an out-of-range value fails with a finding naming the parameter and its range;
      a valid `set` turns the Stage and everything below it `stale`.
- [ ] `decide` with data that doesn't match the schema fails and appends nothing.
- [ ] `decide`, `undo`, `redo`, `undo` leaves the expected current Decisions, and the journal only ever grew.
- [ ] A journal with two entries sharing a parent (written as a merge would) shows `needs-review` with its reason, and
      `next` names the owner action.
