---
status: todo
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

- [ ] CLI seam: two Loops, one complete and one with a flood and no `cycle`. The complete Loop's strip is built, the held
      Loop's `region.png` equals its flood, `check` gives `loop.held` with a `fix` or `owner_action`, and `export` refuses
      the room.
- [ ] CLI seam: after the missing `cycle` Decision, both Loops build and `export` runs.
- [ ] CLI seam: an exported Loop whose ID a new Look then takes gets advice that names the Look, not the Loop.
- [ ] `tests/cli/test_loops.py`'s existing tests pass, changed only where a whole-Stage `needs-input` is now `loop.held`.
- [ ] `lint-imports` and `mypy` pass.

Budget: 80–150k tokens.
