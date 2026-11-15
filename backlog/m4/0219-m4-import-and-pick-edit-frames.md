---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0193-m4-loop-kit-and-import.md, 0129-m4-look-variants.md]
---

# M4: import and pick a Loop's edit frames

Part of [0183](0183-m4-ambient-animation.md), route (c): 0193's Part B, kept by trial
[0184](0184-m4-ambient-animation-trial.md). Spec §10 (Commands) and §6.1 (Looks: `import --look`, `pick --look`).

The Owner made a TV's news broadcast from six image-model edits of the kitchen's Source, in about 15 minutes. It was the
Loop that made the room feel most alive. The edits were made one from another, and each was worse than the last (median ΔE
outside the screen 1.65, 2.61, 3.65, 4.67). So an edit frame must be an edit of the Source.

## What to build

- `kiripix import <id> <png> --loop <loop> --frame <n>` (n from 1; frame 0 is the room and is never imported): adds a
  Variant of that frame, as `import --look` adds one of a Look.
- `kiripix pick <id> <variant> --loop <loop> --frame <n>`: chooses it, recording the hash of the room's Source. A new Source
  puts every edit frame in `needs-input` ("made on another Source").
- **Made from the Source.** On `import --loop --frame`, compare the edit with the Source outside the Loop's region, after
  resizing it to the Source's size (`resize_nearest`). If its median ΔE there is more than twice the first imported frame's
  and over 2.5, an info finding `import.edit_of_an_edit` says so, with the owner_action "make each edit from the Source,
  not from another edit". In the trial, the first edit measured 1.65 and the chained ones 2.61 to 4.67.
- A frame Loop's `frames` Decision takes `source: "edits"`. A frame Loop's frames come from one source only: a kit and edit
  frames on the same Loop are refused.
- `describe`, the Commands' schemas and contract samples; `next` names `import --loop --frame` for an edits Loop with a
  frame missing.

## Acceptance criteria

- [x] CLI seam: two edit frames imported and picked; a new Source puts them in `needs-input`.
- [x] CLI seam: importing frame 0 is refused; a frame made from another edit (a test image with its outside changed by
      more) raises `import.edit_of_an_edit`.
- [x] Contract samples for the new flags pass.

Budget: 80–130k tokens.

## Result (2026-11-14)

- **Where edit frames are stored (chosen).** `src/loops/<loop>/edits/<n>/<hash>.png`, one folder per frame, content-addressed
  as a Look's edits are; `import --loop <loop> --frame <n> <png>` stores it (a JPEG becomes a PNG) and records the file name in
  `imported.jsonl`. The kit's frames stay in `src/loops/<loop>/<hash>.png`, and the stage's `KIT_GLOB` already hashes both.
  Frame 0 (or less) is refused: `import.frame_zero`, `pick.frame_zero`. The core code is `kiripix/core/loopedits.py`
  (`import_edit`, `pick_edit`); the Commands take `--loop`, `--frame` on `import` and `pick`.
- **Rename (chosen).** The same way as a kit: `apply_edits` marks each earlier `pick` Decision of a renamed Loop with `was`
  (the folder ID the file is in, set once), and the held reason reads `src/loops/<was or ID>/edits/<n>/`. For a Variant that is
  imported and not yet picked when the Loop is renamed, core looks under every ID the Loop has had (`former_ids`, from the
  journal's `rename` Decisions), and `pick` records `was` when it found the file under an older ID. Imports after a rename go
  under the new ID.
- **The `pick` Decision** (`loops` Stage; `loop`, `frame`, `variant`, `source` = the room's Source when picked, `was` optional)
  and `frames` `source` `edits`. A Loop is an edits Loop when its `frames` Decision says `edits`, or it has no `frames` Decision,
  no kit and a Pick (`frames_source`, `is_edits`). The latest Pick of a frame counts.
- **Held reasons** (`_held_edits` in `HELD_REASONS`, before `_held_frames`, so `loop.held`, `next`, `export.loop_held` and the
  region file follow): "made on another Source" (any Pick whose `source` isn't the room's current Source; the owner_action names
  the import and pick of each such frame), a frame with no Pick below the highest picked one (a `command` `pick` when exactly
  one edit of that frame is stored, else an `owner_action` naming `import --loop --frame`; with no Pick at all, frame 1), a picked
  file gone. **When every frame is picked the Loop is still held**, with "built in a later ticket (0220)": the build of edit
  frames is 0220's, so nothing here builds them.
- **One source only.** `import --loop` without `--frame` is refused (`import.loop_source_mixed`) for a Loop whose frames are
  edits; `import --frame` and `pick --frame` are refused for a Loop whose frames are a kit or an Op (same code, `import.` or
  `pick.`). Other refusals: `import.frame_needs_loop`, `import.edit_takes_one_image` (not with `frames`, `--kit`, `--look`, `--role`),
  `pick.loop_needs_frame`, `pick.loop_or_look`, `pick.loop_unknown`, `pick.loop_not_frames`, `pick.unknown_variant`.
- **`import.edit_of_an_edit`** (info, `owner_action` "Make each edit from the Source, not from another edit."): the edit is resized
  to the Source's size (`resize_nearest`), fitted as the room's Source was (no registration), and its median ΔE (the 3x3 mean
  of `difference_map`) outside the Loop's region is measured against the room's fit. Over 2.5 and over twice the first imported
  edit's (the oldest file of any frame of the Loop, by file time) raises it. The first edit has nothing to compare with.
  A Loop with no region yet can take edit frames: the whole room counts as outside (`loopkit.prepare(need_region=False)`).
- `describe room --stage loops` lists the `pick` Decision and says `frames` takes `source` `edits`; schema and `import`/`pick`
  descriptions show `--loop`, `--frame`; spec §10 command list updated.
- Tests: `tests/cli/test_loop_edit_frames.py` (7), a contract sample in `tests/cli/test_contract.py`
  (`test_import_and_pick_of_an_edit_frame_validate`).
- For 0220: a Loop's edit frames are `edit_picks(run, loop)` (frame to Pick data); the file is
  `edit_path(pick.get("was", loop), frame, variant)`; `current_source(run)` is the Source they must be made on. Remove
  the final "built in a later ticket" hold in `_held_edits` when the build exists. For 0221 (UI): the `import` result has
  `frame`, the `pick` result `loop` and `frame`.

