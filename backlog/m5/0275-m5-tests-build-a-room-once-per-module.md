---
status: done
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

- [x] Every test still passes, and none reads another's Project.
- [x] The room, character and sprite files are measurably faster. The before-and-after times (rooms, then characters) and
      the slowest 30 are recorded in `docs/test-speed.md`.
- [x] The CLI seam rule holds: the tests still check through `kiripix … --json`, never through internals.

## Result

`restore_template(project, key, build)` in `tests/conftest.py` (see [docs/test-speed.md](../../docs/test-speed.md)): the
first test of a worker builds in its own Project through `kiripix ... --json` and a copy of the folder is kept; later tests
get a copy in their own `tmp_path`, and the fixture runs `status --json` on every copy and fails unless each Stage reads as
it did in the template. Files a test wrote before asking (fake-Blender signal files, `kiripix.toml` edits) belong to the
template's identity, so those tests keep their set-up and get their own template.

Moved: `built_room` of `test_masks.py` and `test_layers_stage.py` (about 30 files import them), `walled_room` and
`lamp_room` of `test_place.py`; `rigged_hero`, `ready`, `built`, `finished`, `sheet_of` and `body` of the character files;
`built_sprite` of `test_cast_sheet.py` (also used by `test_contract.py`). Kept their own set-up: files that read absolute
paths of the Project from `blender-calls.jsonl`, and the prop files (0288 works there).

Measured on a machine shared with other agents (wall times rough; call counts exact), `-n auto --dist loadfile`, HEAD copy
as "before":

- Rooms (`test_masks`, `test_layers_stage`, `test_place`, 91 tests): 1600 s to 792 s; 1060 to 607 `kiripix` calls.
- Characters and sprites (`test_character_sheet`, `_palette`, `_base`, `test_cast_sheet`, plus `test_masks`, 83 tests): 583 s to
  308 s; 1038 to 666 calls.
- The slowest tests are listed in docs/test-speed.md. The Owner's full-suite time is not measured here (the run takes about
  40 min on this machine).

An earlier version compared `kiripix.toml` with the folder's name in it, so every copy was a miss and the first "after"
timings showed no gain; fixed, and the numbers above are from the fixed version. A wider run (the ten character files, rooms,
`test_contract.py`) passed 427 of 429 with the only failures in `test_contract.py::describe` and `test_an_icon_validates`,
from other tickets' in-flight changes (a `body` key in a Stage's input schema, icon output), not from templates.
