---
status: done
milestone: M6
agent: imaging-engineer
type: ticket
---

# M6: cheaper Checks on a character's frames and sheet

Spec §8 (Checks). Part of the Owner's report of 2026-11-21 that the UI is slow again; see
[0366](0366-m6-watch-the-project-without-scanning-it.md). [0367](0367-m6-keep-check-results.md) keeps Check results
until an output changes, so this ticket is about the first call after a rebuild, which is what the Owner waits for after
every render, finish or palette run, and what a cold cache pays for every character.

The work is in Check code: `kiripix/checks/ramps.py` and `kiripix/ops/colour.py`, and the `check` functions of the
character recipes (`kiripix/recipes/character_sheet.py`, `character_finish.py`, `character_palette.py`). Their `run`
functions and what the Stages write are left alone, so no Stage `version` changes.

## What was measured (2026-11-21)

Profiles in the art Project (`mc03_female` has 5,487 files; its `palette` and `finish` Stages hold about 1,360 frames).

`check character.mc03_female` (6.6 s in all):

| Where | Cumulative |
|---|---|
| `_check_colour_atlas` (`character_sheet.py:249`) | 4.09 s |
| of which, the `ndarray.sort` inside `np.unique(..., axis=0)` | about 4.0 s |
| `_check_finish` (`character_finish.py:610`) | 1.06 s |
| `_check_palette` (`character_palette.py:424`) | 0.57 s |
| `read_rgba` (`recipes/common.py:57`), 2,720 calls | 0.84 s |
| `ops.colour.conformance`, 1,360 calls | 0.42 s |

`queue` over the whole Project (the character Checks that ran in it):

| Where | Cumulative |
|---|---|
| `_check_palette` | 2.08 s |
| of which `check_ramp_shared` (`checks/ramps.py:24`), 928 calls | 1.07 s |
| `np.isin`, 41,518 calls | 1.13 s |
| `_check_finish` | 1.51 s |
| `read_rgba`, 3,719 calls | 1.12 s |

## What to do

1. **`sheet.colour_atlas_rgba`** counts the atlas's colours with `np.unique` over RGBA rows, which sorts every pixel. The
   finding only needs the count, and only when there are more than 256. Pack each pixel into one `uint32` and count
   distinct values (`np.unique` on a 1-D array, or PIL's `Image.getcolors`, which is C and can stop early). The finding's
   `colours` stays the exact count.
2. **`check_ramp_shared`** calls `np.isin` once per part per frame, over every pixel. The ramps and parts are the same for every
   frame, so build the lookup once per Check (a label-to-part table indexed by label, and a packed-colour-to-ramp table) and
   index into it per frame, or check the distinct (label, colour) pairs of a frame instead of its pixels.
3. **Read each frame once per Check.** `_check_finish` and `_check_palette` each read every frame through `read_rgba`, and
   `_vanishing_parts` and `_read_labels` read more. Where one Check reads the same file twice, read it once.
4. Anything else the profile shows above 0.2 s, after 1–3.

The findings must not change: the same codes, messages, positions, `data` and order.

## Acceptance criteria

- [ ] `check character.mc03_female --json` and `queue --json` on the art Project give output identical to the code before
      the change (`cmp`), with `.kiripix/derived-cache.json` deleted first if 0367 is done.
- [ ] The profile tables above are recorded again in the Result.
- [ ] The existing tests pass unchanged: `tests/cli/test_character_sheet.py`, `test_character_palette.py`,
      `test_character_ramps.py`, `test_palette_table.py`, `test_sprite.py` and `tests/golden/test_part_ramps.py`. If
      `test_part_ramps.py` doesn't yet call `check_ramp_shared` on a frame with a fixed material and a pixel of one part in
      another part's ramp, it gains that case.
- [ ] `uv run mypy` and `uv run lint-imports` pass.

## Result

Done 2026-11-21. No Stage `run` or output changed, so no `version` bump.

- `sheet.colour_atlas_rgba` (`character_sheet.py`, `_check_colour_atlas`): each RGBA pixel is viewed as one `uint32` and
  `np.unique` counts the 1-D values, instead of sorting 4-column rows. The count is the same exact number.
- `check_ramp_shared` (`checks/ramps.py`): new `RampLookup(parts, ramps)`, built once per Check (the shared-colour pairs, a
  sorted table of every ramp colour with a colour-by-ramp membership matrix, and a per-part boolean table indexed by label).
  `check_ramp_shared` takes it as an optional last argument (without it, it builds one, so the signature still works), and per
  frame it keeps only the opaque pixels that have some ramp colour, then looks up part and ramp for those. `_check_palette`
  builds it on its first frame and passes it on. Same findings, same order, first pixel still row-major.
- `_check_finish`: `_vanishing_parts` keeps the material frames of the front views it reads and `_covered_eyes` takes them from
  there, so each material frame is read once. The colour and normal frames were already read once per Check; `_check_palette`
  reads each frame and label once, so nothing to merge there.
- Item 4: `ops.colour.conformance` counted the palette with `np.isin`, which loops over the palette's entries for a small
  palette; it now uses a sorted palette and `searchsorted` (2x faster on 256x256 with 64 colours, same result).
  `read_rgba` is PNG decoding and file reads; nothing to remove there once each file is read once.
- New golden case in `tests/golden/test_part_ramps.py`: one frame with a hair pixel in the boots' ramp and a fixed material
  with a hair colour and a boots colour; it pins the findings' order, first pixels and counts.

Identical output: `check character.mc03_female --json` and `queue --json` on a copy of the art Project (`cmp`, with
`.kiripix/derived-cache.json` deleted before each run) are byte-identical between the code before this ticket (the working
tree with only these edits reverted) and after.

Profiles (cProfile cumulative seconds, cold, same copy). The machine was heavily loaded by other agents' tests while these
ran, so every figure is several times the ticket's (the unchanged `read_rgba` shows it: 2.9 s here, 0.84 s then). Compare
the rows of one column pair, not the ticket's table; wall time of the same Commands was 209 s before and 19 s after for
`check`, 182 s and 71 s for `queue` under that load.

`check character.mc03_female`:

| Where | Before | After |
|---|---|---|
| `_check_sheet` | 21.36 s | 1.20 s |
| of which `_check_colour_atlas` | 20.27 s | 0.16 s |
| `_check_finish` | 4.35 s | 3.20 s |
| `_check_palette` | 2.05 s | 1.64 s |
| `read_rgba`, 2,720 calls | 3.50 s | 2.91 s |
| `conformance`, 1,360 calls | 1.53 s | 0.95 s |
| `np.isin` from `conformance`, 1,360 calls | 0.79 s | 0 |

`queue`:

| Where | Before | After |
|---|---|---|
| `_check_palette` | 12.16 s | 12.13 s (ramp part below) |
| of which `check_ramp_shared`, 928 calls | 6.26 s | 2.38 s |
| `np.isin`, calls | 6.87 s, 41,518 | 0.24 s, 684 |
| `_check_finish` | 11.52 s | 13.29 s (load noise) |
| `read_rgba`, 3,721 calls | 8.90 s | 11.21 s (load noise) |
| `conformance`, 1,858 calls | 3.66 s | 4.25 s (load noise) |

What is left is PNG decoding (`read_rgba`) and the per-frame work of `conformance`, `_vanishing_parts` and the ramp lookups;
the rest of the Check time is 0367's to skip when nothing changed.

Tests: `tests/golden/test_part_ramps.py` (13), `tests/cli/test_character_sheet.py`, `test_character_ramps.py`,
`test_palette_table.py` pass; `test_character_palette.py::test_the_check_is_clean_after_a_run_and_names_the_frame_when_one_is_off`
fails only because 0367's findings cache (now in `graph.check`) keeps the findings after the test edits an output file
without a rebuild (not from this change); `test_sprite.py` errors/fails in 0362's unfinished work (e.g. a blank-frame
effect test). `uv run mypy` and `uv run lint-imports` pass.
