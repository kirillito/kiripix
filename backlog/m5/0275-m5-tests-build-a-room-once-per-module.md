---
status: todo
milestone: M5
agent: qa-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: tests: build rooms, characters and sprites once per test module, and copy them for each test

[docs/test-speed.md](../../docs/test-speed.md) ("Still open: build rooms once per test module"). The full suite takes 80–90
minutes on the Owner's laptop (the M4 gate, 2026-11-16), so a run per batch costs most of an afternoon.

## The gap

About 50 CLI test files build a room for every test through subprocess calls (`built_room` is defined per file, in
`test_masks.py`, `test_layers_stage.py` and others). Each call pays Kiripix's start-up (about 1 s), and a built room takes
many calls. The tests then change only what they test.

## What to build

- A module- or session-scoped fixture that builds each kind of room the tests need once (imported, fitted, Layers, Masks,
  palette, placed, to whichever Stage the module needs) into a template folder, and a function-scoped fixture that copies
  the template into the test's own `tmp_path`. Every test still gets its own Project, so tests stay independent and run
  under `-n auto --dist loadfile`.
- The copy must keep what status reads (the hash cache and journals) so the copied room is `done` where the template was.
  Check with `status --json` in the fixture, and fail the fixture if it isn't.
- Move the per-file `built_room` fixtures to it, one file at a time. A file whose tests need a room built differently keeps
  its own.
- **Then the same for characters and sprites**, which build on the fake Blender in every test (`test_character_*.py`,
  `test_sprite.py`, `test_cast_sheet.py`, `test_palette_table.py` and others). Make templates for the common built states:
  - a character through `render`, and through `sheet`;
  - a base and a character made from it;
  - a sprite from the fixture ZIP through `sheet`.
- Do the rooms first and measure, so the gain is known before the characters are moved.
- Record before and after in `docs/test-speed.md`: the suite's time with `-n auto --dist loadfile`, and `--durations=30`.

## Acceptance criteria

- [ ] Every test still passes, and none reads another's Project.
- [ ] The room, character and sprite files are measurably faster. The before-and-after times (rooms, then characters) and
      the slowest 30 are recorded in `docs/test-speed.md`.
- [ ] The CLI seam rule holds: the tests still check through `kiripix … --json`, never through internals.
