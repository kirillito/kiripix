---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0184-m4-ambient-animation-trial.md, 0189-m4-loops-stage.md, 0129-m4-look-variants.md]
---

# M4: the loop kit, and importing frames

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §10 (Commands) and §6.1 (Looks: `import --look`, `pick --look`).
Two Owner-made frame sources: a kit painted by hand at target size, and image-model edits of the Source. 0194 builds them.

**Part B (edit frames) is the most cuttable work in 0183.** If the trial (0184) finds that edit frames flicker too much to
use, cut Part B and say so in 0183.

## Part A: the kit

- `kiripix loop kit <id> <loop> <folder> --frames N`: writes `frame_000.png` (the region's box at target size, from the room
  after `palette`, alpha 0 outside the region), copies `frame_001.png` … `frame_<N−1>.png` to paint on, `palette.gpl`,
  `palette.png` (a swatch strip) and a `README.txt` of three lines (paint on copies, stay in the box, use only the palette).
  It refuses a folder that already has frames unless `--force`. Not owner-only: an agent may prepare a kit.
- `kiripix import <id> <png…> --loop <loop>`: reads frames 1 … N−1 in name order (frame 0 is always the room's and is never
  imported; a `frame_000.png` among them is skipped with an info finding). Each must be the box's size exactly
  (`import.size_mismatch` otherwise). It records the hashes of the frames, the fit and the palette they were painted on.
- Staleness: a refit puts kit frames in `needs-input` ("painted on another fit"); a palette change keeps them and 0194 remaps
  them (`needs-review`).

## Part B: edit frames

- `kiripix import <id> <png> --loop <loop> --frame <n>`: adds a Variant of that frame, as `import --look` adds one of a Look.
- `kiripix pick <id> <variant> --loop <loop> --frame <n>`: chooses it, recording the hash of the room's Source. A new Source
  puts every edit frame in `needs-input` ("made on another Source").

## Both

- `describe`, the Commands' schemas and their contract samples; `next` suggests `loop kit` for a `frames` Loop with no source.

## Acceptance criteria

- [x] CLI seam: `loop kit` writes the files above; frame 0 equals the room in the box; a second run without `--force` is refused.
- [x] CLI seam: importing painted frames records them; a wrong size is refused; a refit puts them in `needs-input`.
- [ ] CLI seam (Part B): two edit frames imported and picked; a new Source puts them in `needs-input`. **Not done: the Owner decided (2026-11-13) to leave Part B until trial 0184 has run.**
- [x] Contract samples for `loop kit` and the new flags pass (Part A).

Budget: 150–250k tokens (Part A alone: 90–150k).

## Result (Part A, 2026-11-13)

Part B is left until trial 0184 has run (the Owner's decision).

- **`kiripix loop kit <id> <loop> <folder> --frames N`** (`commands/loops.py`, `core/loopkit.py`): writes `frame_000.png` (the region's
  box from the room after `palette`, alpha 0 outside the region, cut to the Layer's alpha for a Loop on a Layer), copies
  `frame_001.png` ... , `palette.gpl`, `palette.png` (8 px swatches in one row), a three-line `README.txt` and `kit.json`
  (`schema_version`, asset, loop, box, frames, `fit`, `palette`). Refused: `loop.kit_exists` (a folder with frames, unless
  `--force`, which also removes frames beyond N), `loop.kit_unknown` (a `fix` declares it), `loop.kit_not_frames`,
  `loop.kit_no_region`, `loop.kit_needs_build` (fix: run the Stage), `loop.kit_frames` (N outside 2 to 64). `--frames` defaults to 4.
- **`import <id> <png> [<png>...] --loop <loop>`**: `import` gained `--loop` and a positional `frames` (more PNGs; over REST a JSON
  list of paths on the server's machine, not multipart, so 0196 must upload another way or add multipart lists). Sorted by name;
  `frame_000` skipped with the info finding `import.frame_zero_skipped`; `import.size_mismatch` (nothing is stored), `import.loop_unknown`,
  `import.loop_no_frames`, `import.loop_region_changed` (the box differs from the kit's `kit.json`), `import.frames_need_loop`,
  `import.loop_takes_images`. Output gains `loop`, `loop_frames` (stored names), `skipped`.
- **Where the records live:** frames are `src/loops/<loop>/<hash16>.png` (content-named, a Stage input through `files` in
  `room.py`); the record is a `kit` Decision in `decisions/loops.jsonl`:
  `{loop, box:[x,y,w,h], frames:[<hash16>...] (frames 1..N-1 in order), fit, palette}`. `fit` is the first 16 hex of the SHA-256 of
  `work/fit/fit.png`; `palette` that of the sorted unique palette colours. They come from `kit.json` when it sits beside the
  frames, else from the room as it is. The Decision is `KIT_DECISION` in `recipes/kit_record.py`; the latest per Loop counts. Names
  imported with go to `imported.jsonl`.
- **Staleness** (`kit_needs_input`, hooked at the top of `_frames_needs_input` in `recipes/loops.py`): a missing frame file, or a
  `fit.png` that differs from the record, is needs-input "painted on another fit" (owner_action: new kit or undo). A palette change
  keeps the kit; `kit_record.palette_moved(run, kit)` is what 0194 asks to remap (`needs-review`). The kit is ignored when the
  Loop's `frames` Decision has `source` other than `kit`.
- **`next`:** a frame Loop with no `frames` Decision and no kit gives needs-input with `command` `kiripix loop kit <id> <loop> kits/<loop> --frames 4`.
- Tests: `tests/cli/test_loop_kit.py`; samples in `test_contract.py` (`loop kit`, an `import --loop` schema test) and `BODIES` in `test_serve.py`.
- **For 0194:** a region that moved after import isn't caught by the Stage (only `import` compares boxes); check each frame's size
  against the built box when building.

## Closing notes (2026-11-13)

- Closed 2026-11-13 with Part A; Part B (edit frames) waits for trial 0184, the Owner's decision.
