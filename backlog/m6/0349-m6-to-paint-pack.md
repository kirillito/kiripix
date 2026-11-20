---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0348-m6-brief-renders-the-prompt.md, 0327-m6-match-scope.md]
---

# M6: `kiripix to-paint`: every prompt and canvas a district needs, in one folder

Spec §10.5 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). The name `to-paint` is a placeholder;
the Owner may rename it.

## The gap

To paint a district's Sources, the Owner visits each room for its prompt, and for a multi-screen room runs
`extend <id> canvas` for each side. With 30 rooms, that's the session work the Owner does before any first pass can start.

## What to build

A Command that records nothing: `kiripix to-paint --match <glob> [--out <folder>]` (default
`.kiripix/to-paint/<date>/`). For every matched room waiting on its Source, it writes:

- **A room with no picked Source and no `extend` in progress:** `<nn>-<room>.prompt.txt` (the brief's prompt from
  [0348](0348-m6-brief-renders-the-prompt.md)).
- **A room with an `extend` in progress:** its next canvas, as `extend <id> canvas` would write it for the side the brief's
  size still needs (`<nn>-<room>.<side>.png`), with its prompt.
- **`index.md`:** one line per room in the order to paint, saying what to make and **what to name the file that comes back**
  (`<room>.png`, `<room>.<side>.png`), so [0350](0350-m6-source-inbox.md)'s inbox files it.
- A room with no brief is listed under "no brief yet", with the command to write one. A room whose Source is picked isn't
  listed.

## Acceptance criteria

- [ ] CLI seam: a district of three test rooms (one with no Source, one mid-`extend`, one done) gives one prompt, one canvas
      and an index with two entries and their return names.
- [ ] CLI seam: nothing in the Project changes (input hashes and journals as before).
- [ ] `to-paint` has a sample in `tests/cli/test_contract.py`; spec §10.5 lists it.
