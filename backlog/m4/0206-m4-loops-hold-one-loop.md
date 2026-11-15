---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0189-m4-loops-stage.md, 0194-m4-loops-build-imported-frames.md]
---

# M4: a Loop that can't build holds itself, not the `loops` Stage

Found by [0191](0191-m4-ui-loops-screen.md) (2026-11-13), its gap 2. Spec §6.1 (`loops`). Today, a Loop with no `cycle`, a
`rotate` under two colours, or a `ticks` list of the wrong length puts the whole Stage in `needs-input`. The other Loops
aren't built, and a region the Owner flooded first isn't drawn until the cycle is valid. That costs the Owner time on every
new Loop.

## What to build

- **Hold one Loop.** Each held reason in `loops_needs_input` (`kiripix/recipes/loops.py`) that concerns one Loop now holds
  only that Loop: no `cycle`, too few colours, a repeated colour, a bad `ticks` list, a frame Loop with no source, a kit
  painted on another fit, a `layer` the room lacks, an ID clash with a Look. The Stage builds the other Loops.
- **Show its region.** For a held Loop, the Stage writes its region (`<loop>/region.png`, room size, 1-bit) and its `box`,
  and lists it in `loops.json` with `held` (the reason) and no frames.
- **Finding.** Each held Loop raises `loop.held` (error), with today's `fix` or `owner_action` for that reason. `next`
  points at it.
- **Export.** A held Loop isn't exported, and `export` refuses the room while any Loop is held, with a finding that names
  the Loop. A frozen Loop must never drop out of the scene silently.
- **The clash's advice.** The `owner_action` for a Loop that shares a Look's ID names both ways out: give the Loop another
  ID, or give the Look another ID (undo its `pick` in `looks`). When the Loop's ID is already in the Manifest, only the
  second applies.
- **`describe room --stage loops`:** the `loop`, `cycle` and `timing` Decisions each say that the latest one replaces the
  whole Decision before it, so it must carry every field.

## Acceptance criteria

- [x] CLI seam: two Loops, one complete and one with a flood and no `cycle`. The complete Loop's strip is built, the held
      Loop's `region.png` equals its flood, `check` gives `loop.held` with a `fix` or `owner_action`, and `export` refuses
      the room.
- [x] CLI seam: after the missing `cycle` Decision, both Loops build and `export` runs.
- [x] CLI seam: an exported Loop whose ID a new Look then takes gets advice that names the Look, not the Loop.
- [x] `tests/cli/test_loops.py`'s existing tests pass, changed only where a whole-Stage `needs-input` is now `loop.held`.
- [x] `lint-imports` and `mypy` pass.

Budget: 80–150k tokens.

## Result (2026-11-14)

- **Per-Loop holds.** `loops_needs_input` now holds the whole Stage only for a Decision naming an undeclared Loop. Every
  other reason is one function of `LoopInputs` in `HELD_REASONS` (`kiripix/recipes/loops.py`): `_held_id_clash`,
  `_held_layer`, `_held_frames` (no frames, kit missing or painted on another fit, a `difference`, a timing of the wrong
  length), `_held_cycle` (a `frames` Decision, no cycle, under two colours, a repeated colour, a timing of the wrong
  length, a `difference`) and `_held_difference_box`. `held_loops(run)` returns each held Loop with its `NeedsInput`; the
  first reason that answers holds it. A new reason (0207, 0219, 0222, 0223) is one more function in that tuple.
- **`loops.json`** (schema_version stays 1; the keys are additive, readers use `.get`): every record has `held` (null, or
  the reason). A held record has `frames` 0, no pieces, its `box` and `region` (`<loop>/region.png`, room size, 1-bit,
  cut to its Layer's alpha when the room has it), `held_fix` or `held_owner_action`. The Stage's message names the
  held Loops.
- **`loop.held`** (error, `fix` for a command such as `loop kit`, else `owner_action`; position `field` `loop.<id>`
  with the box). `run loops` ends done and exits 2 because of it; `next` points at it, as it does for any error finding of a
  done Stage. The other Loops build.
- **Export.** A held Loop is left out of `room.json`, and `export.loop_held` (error, same remedy) refuses the room, besides
  `loop.held` itself failing `kiripix export`'s readiness check. The ID freeze still sees the Loop (its ID comes from
  the Decisions).
- **The clash's advice** names both ways out. A Stage can't read the game's Manifest, so core gained a small hook,
  `register_adviser` in `kiripix/core/graph.py` (`AssetGraph.check` passes a Stage's findings through the advisers), and
  `kiripix/export/checks.py` registers one: a held Loop whose ID the Manifest lists and a Look has gets only the Look's
  way out.
- `describe room --stage loops`: `loop`, `cycle` and `timing` say the latest Decision replaces the whole one before it.
- Tests: `tests/cli/test_loops.py` (a held Loop and a built one, the region, `next`, the clash advice), `tests/cli/
  test_export_loops.py` (export refused while held, and builds once the cycle is given; the exported Loop's ID taken by a
  Look). Whole-Stage `needs-input` expectations became `loop.held` in `test_loop_kit.py`, `test_loop_kit_frames.py` and
  `test_loop_frame_ops.py`.
