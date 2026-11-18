# Test speed

The full suite took 34 minutes on 2026-11-03 (405 tests, on Windows), before tickets 0019 and 0020 added about 60 more.
The time goes to the CLI seam, not to the logic. Each CLI call in a test starts a new Python process, and one room test
makes many of them: `test_place.py` and `test_reachability.py` took about 16 s per test, while the golden tests take
milliseconds.

The full suite runs once at the end of a batch of tickets, and single test files run until then.

## Done

1. **Run tests in parallel with `pytest-xdist`** (ticket 0068, M2): `uv run pytest -n auto --dist loadfile`.
   `--update-golden` still runs without `-n`.
2. **Trim the start-up time of `kiripix`** (ticket 0163, M4): heavy modules (numpy, jsonschema, the weights download) load
   on first use, so every CLI call pays less. What is left is pydantic and typer, which the contract needs; the 0.3 s goal
   for `kiripix --help` would need a different path for them, and is left for a follow-up if still wanted. The M4 gate
   records `kiripix --help`'s and the full suite's times on the Owner's laptop.
3. **Import a Command's module only when it runs** (ticket 0277, M5): a static index of the Commands
   (`kiripix/commands/index.py`) and a CLI that builds Typer's parameters only for the called Command. `kiripix --help`
   went from 0.47 s to 0.14 s, `kiripix status --json` from 0.48 s to 0.40 s (pydantic, typer and the stage graph are
   what is left).

## Still open

Nothing scheduled.

## Templates: build a room, character or sprite once per worker (ticket 0275, M5)

`restore_template(project, key, build)` in `tests/conftest.py`. The first test of a worker that asks for a built state
builds it in its own Project, through `kiripix ... --json`, and a copy of the folder is kept as the template. Each later
test gets a copy into its own `tmp_path` (so tests stay independent and run under `-n auto --dist loadfile`) and the fixture
runs `status --json` on the copy: it fails unless every Stage reads as it did in the template. What a test put in the
Project before asking (a fake-Blender signal file, a setting in `kiripix.toml`) is part of the template's identity, so a
test that sets `blender-materials` first gets its own template. The Project's name, taken from the folder, is left out of
that and rewritten in the copy. Templates in use: the room through `masks` (`built_room` in `test_masks.py` and
`test_layers_stage.py`, which about 30 files import), the walled room and the lamp room of `test_place.py`, the hero
through `rig`, `clips`, `palette`, `finish` and `sheet`, the base, and sprite.npc through `sheet`. Files whose tests build
differently keep their own set-up (for example the ones that count absolute paths in `blender-calls.jsonl`).

Measured on 2026-11-17 and 2026-11-18, on a Windows machine that other agents were also using (runs of the same files
differed by 2x, so the wall times are rough; the count of `kiripix` calls is exact). "Before" is the HEAD version of the
tests, run from a copy; `-n auto --dist loadfile`, one file per worker.

| Set | Tests | Wall time before | after | `kiripix` calls before | after |
|---|---|---|---|---|---|
| Rooms: `test_masks`, `test_layers_stage`, `test_place` | 91 | 1600 s | 792 s | 1060 | 607 |
| Characters and sprites: `test_character_sheet`, `_palette`, `_base`, `test_cast_sheet`, plus `test_masks` | 83 | 583 s | 308 s | 1038 | 666 |

The rest of the 30 slowest are the same files' longest tests, which build more than the shared state (a click, a lift, an
accept, a `place`). The slowest before: `test_place.py::test_a_link_end_on_solid_reports_link_not_walkable_naming_the_end`
91 s, `test_layers_stage.py::test_an_add_that_needs_a_fill_stops_for_review...` 88 s, `test_place.py::test_a_sloped_line_...`
77 s; after: `test_place.py::test_a_marker_is_refused_without_the_fields...` 68 s, `test_place.py::test_a_layer_with_no_line_fails_...`
63 s, `test_layers_stage.py::test_min_piece_...` 50 s (those times come from a machine at times 10 times slower than the
Owner's laptop). The full suite after the batch (2026-11-18, `-n auto --dist loadfile`, on the Owner's laptop while
it was also running other work): 1 h 22 min for 2,107 tests, against the M4 gate's 80-90 min, which had about 300 fewer.
Not a clean measure; the next unloaded run should replace it, with `--durations=30`.

## The real-Blender render tests (ticket 0281, M5)

`tests/cli/test_blender_render.py` (7 tests, marked `blender`) took about 3.5 minutes on 2026-11-17 on the Windows dev
machine with Blender 5.2.3, rendering with `--cpu` while other agents used the machine (runs of 202 to 246 s), against the
ticket's goal of under two minutes on the Owner's GPU, which is not yet measured. Where it goes: one shared render of 17
clip frames in 8 directions at 64 px for six of the tests (about 80 to 120 s, in the module fixture's set-up) and the base's
height-ratio test (about 75 to 105 s: two characters, each with `model`, `rig`, `clips` and `render` Blender runs). Each
Blender start costs several seconds, so the number of Blender runs matters more than the frames. The Model is 270 faces,
so shrinking it would not help. `--cpu` is the cost here: the Owner's run on the GPU is the number to record.
