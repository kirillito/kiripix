---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0362-m6-sprite-effect-parameters.md, 0370-m6-export-clip-ticks.md]
---

# M6: `import --role sheet` reads a Pixelbolt atlas

Spec §6.4 (the `sprite` Kind, `frames`) and §14 (M6, battle effects). P5 of the trial [0347](0347-m6-vfx-trial.md), filed by the
Owner on 2026-11-27. An effect's frames are made with [Pixelbolt](https://github.com/skulitom/Pixelbolt) (MIT), outside
Kiripix, and imported as a sheet. Kiripix runs no Node and doesn't run Pixelbolt (the Owner's verdict on 0347); it only reads
what Pixelbolt wrote.

## The gap

Today the Owner (or a session) imports Pixelbolt's `<name>.png` as a plain sheet and then types what the atlas already says: the
frame layout and count in a `sheet` Decision, each frame's duration as `ticks` in a `clip` Decision (ms x 60 / 1000, by hand), the
loop flag, and the anchor as a `fit` parameter. Every number is in `<name>.atlas.json`, so typing them is slow and a typo shifts
an effect's timing or pivot without a finding.

## Pixelbolt's atlas (read from a 0.19.0 render, 2026-11-20)

TexturePacker-style JSON beside the sheet PNG:

- `frames`: a map from frame name (`<name>-<n>`) to `frame` (`x`, `y`, `w`, `h` in the sheet), `rotated` (false),
  `trimmed`, `spriteSourceSize`, `sourceSize`, `duration` (ms), `anchorPx` (`x`, `y`, the anchor in the frame's pixels),
  and the anchor as fractions (`anchor`, `pivot`).
- `animations`: a map from animation name to `frames` (frame names, in **expanded playback order**: a pingpong is already
  unrolled), `loop` (bool) and `duration` (ms, the whole animation).
- `meta`: `app: "Pixelbolt"`, `version`, `image` (the PNG's file name), `size`, and Aseprite-style `frameTags`.

The Owner uses the latest Pixelbolt release (0.21.0 on npm, 2026-11-27). Recheck the format on the latest release when the
ticket starts, record its version and any difference in the Result, and read `meta.version` so a later format change is a
finding (`import.atlas_version`, info, naming the version read) rather than a silent misread.

## What to build

- `kiripix import <id> <file.atlas.json> --role sheet` on a `sprite`, or a folder holding one `*.atlas.json`: Kiripix
  recognises the atlas by `meta.app == "Pixelbolt"`, finds the PNG `meta.image` names beside it, and stores both whole in
  `src/sheets/` (the JSON beside the PNG). The recipe (`*.pixel.json`, `*.fx.json`) may sit in the same folder; it is copied
  into `src/sheets/` too, as a note, and nothing reads it.
- **One clip per animation**, named by the animation (snake_case, as `clips.bad_name` asks); its frames are cut by the frame
  rects in the animation's order (a frame listed twice is cut once and played twice); `directions=1`. The result records a
  `sheet` Decision from the atlas, as a typed one would be, so `show`, `undo` and the journal see it.
- **Timing:** a `clip` Decision per clip with `loop` from the atlas and `ticks` from each frame's `duration`
  (floor(ms x 60 / 1000 + 0.5), rounded half up, not Python's half-even `round`; at least 1). When the rounding changes a clip's total by more than one tick, an info finding,
  `import.ticks_rounded`, names the clip and the drift.
- **Anchor:** when every frame of the import has the same `anchorPx`, the result's data names it and the finding
  `import.anchor` (info) gives its `fix`: `kiripix set <id> fit anchor=x,y`. Import sets no parameter itself (a parameter is
  the Owner's or a session's `set`). Different anchors across frames are `import.anchor_varies` (warning, naming the frames).
- **Refused, with a finding each:** an atlas whose `meta.image` is missing (`import.atlas_image_missing`); a `rotated` frame
  (`import.atlas_rotated`); a frame rect outside the PNG (`import.atlas_rect`); a JSON that isn't a Pixelbolt atlas, which
  falls back to the plain PNG/ZIP import's error. A `trimmed` frame is placed by `spriteSourceSize` inside `sourceSize`, so the
  cell is the untrimmed one.
- **Re-import:** importing a new render of the same effect replaces the sheet (as a new `sheet` Decision) and the clips' Decisions
  from it, so `undo` steps back to the old render.
- Spec §6.4's `frames` row and §10.5's `import` line say so.

## Acceptance criteria

- [x] CLI seam: a fixture atlas (two animations, one looping, one a one-shot ending on a blank frame, with 50 ms and 70 ms
      frames) imports into a new `sprite` with `fit effect=true`; `run` and `export` build; `character.json`'s clips have the
      atlas's frame order, `loop` and the rounded `ticks`; `import.anchor` gives the `set` command.
- [x] CLI seam: a pingpong animation's repeated frame is cut once and played twice.
- [x] CLI seam: each refusal above, with its code, changes nothing in the Project.
- [x] CLI seam: a plain PNG sheet and a PixelLab ZIP import exactly as before.
- [x] The fixture is made for the test (a few pixels), not a real effect; `lint-imports` and `mypy` pass.

## Result

Done 2026-11-27. Spec §6.4 has the paragraph "A Pixelbolt atlas" and its `frames` row names it; §10.5's `import` line says what a
sprite's sheet may be.

- **`core/atlas.py`** reads the atlas (`import_atlas`, called by the `import` Command for a sprite's `--role sheet`; `find` takes the
  `.json` or a folder with one `*.atlas.json`). A JSON without `meta.app == "Pixelbolt"` returns None, so the plain import runs and says
  `import.sheet_invalid`. Everything is checked before any write; a refusal changes nothing.
- **Storage:** `src/sheets/<hash>.png`, `<hash>.atlas.json`, and `<hash>.pixel.json` / `.fx.json` (a note: the file with the atlas's
  stem). `sheets_of` in `frames` now takes only `.png` and `.zip`, so the JSON and notes are never sheets. The sheet's `imported_as` is
  the atlas's file name.
- (The three bullets on the sheet shape, re-import and `ImportData.atlas` below describe the first version; the review at the end supersedes
  them where it says so: one `sheet` Decision with `clips`, no `clip` Decisions, no retiring, no `retired`.)
- **A third `sheet` Decision shape** (`file`, `cell`, `cells` [`name`, `rect`, `at`], `plays` [clip to cell numbers in playback order]):
  each distinct cell is cut once, set at `spriteSourceSize` on a transparent cell of the largest `sourceSize`, and a repeated frame
  (a pingpong) is the same cell named twice. `clip` Decisions carry `loop` and `ticks`; an `fps` or `stationary` the Owner decided
  for a clip is kept on re-import. No `version` bump: the new shape is read only when a Decision has it, so no existing sprite's output
  or input hash changes. No data file changed (`schema_version` untouched).
- **Re-import:** an atlas with another PNG records a `sheet` Decision with no cells for each earlier atlas sheet (so it stops
  cutting), then the new `sheet` and `clip` Decisions, in one atomic journal write. `undo` steps back one Decision at a time (the same
  count of `undo`s as the import recorded). A PNG that has its atlas beside it is never "undecided", so after undoing the import
  `frames` doesn't ask for input and cuts nothing from the new PNG. The same render again records nothing.
- **Findings:** `import.anchor` (info, `fix` `kiripix set <id> fit anchor=x,y`), `import.anchor_varies` (warning),
  `import.ticks_rounded` (info, drift over one tick), `import.atlas_version` (info; `meta.version` not `1`) and, beyond the ticket,
  `import.directions` (info, `fix` `kiripix set <id> frames directions=1`, since an atlas clip is one direction and a sprite asks for 4
  by default). Refusals: `import.atlas_image_missing`, `import.atlas_rotated`, `import.atlas_rect`, and, beyond the ticket,
  `import.atlas_invalid` (a frame the animations name that the atlas lacks, a bad shape, two animations that are one snake_case name,
  a frame set outside its cell) and `import.atlas_ambiguous` (a folder with two atlases).
- **`ImportData.atlas`** (new, null otherwise) holds the version, image, cell, anchor, the clips (name, animation, frames, cells, loop,
  ticks), the stored files and the retired sheets. `kiripix/commands/index.py` was regenerated (the summary changed). No new Command,
  so no contract or `BODIES` sample.
- **Format recheck (2026-11-27, `npx pixelbolt@latest`, 0.21.0, throwaway renders of the `coin-sparkle` and `effects` presets, outside
  the repo):** the atlas matches the description above (`frames` with `frame`, `rotated`, `trimmed`, `spriteSourceSize`, `sourceSize`,
  `duration`, `pivot`, `anchor`, `anchorPx`; `animations` with `frames`, `loop`, `duration`; `meta`), with these differences:
  `meta.version` is the atlas **format's** version, `"1"`, not the package's (so `VERSIONS = ("1",)`; the 0.19.0 value isn't known
  to me), `meta` also has `format` and `scale`, a frame may have `points`, and the recipe is `<name>.pixel.json` beside it. Per-animation
  `duration` equals the sum of the frames' (the import uses the frames'). No render had a rotated, trimmed or pingpong frame, so those
  paths are tested on the fixture only.
- Tests: `tests/cli/test_import_atlas.py` (19). Existing `test_import_sheet.py`, `test_sprite.py` and the contract, index and serve
  tests were run too.
- Not from this ticket, seen while running the neighbours: `test_import_sheet.py::test_a_sprite_takes_no_pick` (`pick` on a sprite now
  goes to 0390's `gen_sprite.pick`, so `pick.unknown_variant`, not `pick.no_stage`) and the two `test_the_buff_glow_*` tests in
  `test_sprite.py` (`backlog/m6/0347-trial/sheets/buff_glow.png` is gone from the working tree) fail without any change of this ticket.

### Owner's review, 2026-11-27 (fixes)

1. **A refusal writes nothing.** The clip names are checked against `NAME_PATTERN` (`glow-e` is the clip `glow_e`: `import.atlas_invalid`)
   and the `sheet` Decision is checked with the new `editing.check_decision` (the `record_decision` checks, no write) before the first
   file is written. Test: `test_an_animation_whose_clip_name_ends_in_a_direction_is_refused_and_nothing_changes`.
2. **`import.atlas_version`** has an `owner_action` (check the clips against the render), no `fix`.
3. **Re-import is one `undo`.** The journal has no grouping (an `undo` takes one entry), and a format change was not needed: the whole
   import is now **one `sheet` Decision** (`file`, `cell`, `cells`, `plays`, and new `clips`: clip name to `loop` and `ticks`). Only the
   latest atlas `sheet` Decision cuts, so a new render replaces the old, a clip the new render lacks is gone, and one `undo` makes the
   old Decision the latest again (`redo` brings the new back). **Deliberate deviation from the ticket's text:** no `clip` Decision is
   recorded per animation; the atlas's `loop` and `ticks` are the defaults under any `clip` Decision (the frames Stage merges them).
   A `clip` Decision of the Owner's therefore wins, and an `fps` or `stationary` they decided stays without the import copying it.
   The earlier "retire" Decisions (a `sheet` Decision with no cells) are gone. No `version` bump (the shape is read only when a
   Decision has it) and no journal or data-file change. `ImportData.atlas.retired` is removed. Test:
   `test_a_folder_holding_one_atlas_imports_and_a_new_render_replaces_the_sheet_so_one_undo_steps_back`.
4. **Spec:** the `frames` row names the atlas shape and `clip`'s `ticks`; §14 says the atlas import is built (0401); the ticks rounding
   is half up in the spec and here.
