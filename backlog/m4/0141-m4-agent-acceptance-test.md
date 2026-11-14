---
status: done
milestone: M4
agent: qa-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
depends_on: [0137-m4-area-marker.md, 0138-m4-export-area.md, 0140-m4-export-masks-and-room-json.md, 0136-m4-extend-commands.md]
---

# M4: the agent acceptance test takes a room with an area

Spec §14 (the agent acceptance test). It's run at the gate, not in CI.

## What to change

- The stand-in Owner's fixture adds an `area` Marker (`battle.test`, cell 32, `walkable = true`) to the room, so the agent has to place it from
  `describe`, `next` and `check` output alone, and clear `area.no_walkable` if the fixture puts it wrong first.
- The room is two pieces joined with `extend`, from fixture pieces, before `import`.
- The run checks that the export has the `Area2D`, `masks/solid.png` and `room.json`.

## Acceptance criteria

- [x] The harness runs the new steps on the fake Runners.
- [x] The token count is recorded at the gate, against M3's.

Budget: 100–200k tokens to prepare, plus the run at the gate.

## Result (2026-11-13)

Prepared; the run at the gate is the Owner's. The scripted dry run (`uv run python -m tests.acceptance.run --dry-run`) passes
on the fake Runners: 37 commands, `extend canvas`, `add`, `done`, `pick`, then `next` to export and `check --all` clean.

- **Room:** now 240 x 160 in two pieces (`harness.room_pieces`; the canvas is `[144, 160]`, set in `kiripix.toml` by the setup).
  Registration needs textured patches at least 24 px apart along the overlap, with a 16 px search either side, so the canvas
  had to be tall (the 48 x 32 room could never register) and the floor is blobs, not noise: 1 px noise is "orphan pixels" to
  the `palette` Stage and 2 px blocks look like an upscaled grid to `fit`. Four palette colours in all, so there is no
  `palette.mapping_error`. The wall is 32 px wide (brush radius 16), so a 32 px cell can lie wholly on `solid`.
- **Owner fixture:** `owner.json` loses the `pick` entry (the setup picks the first piece, since `extend` grows the picked
  Source; the agent picks the joined Variant, as `extend done` says to) and adds `battle.test` twice: first at (0,0)-(20,20) on
  the wall (`area.no_walkable`), then, when `next` waits at `place`, moved to (40,8)-(70,24), which snaps to (32,0)-(95,31).
  The spawn moved to (64,16), off the wall.
- **Harness:** the task asks for the second piece (`{piece}`) and the area; the scripted agent does the `extend` steps and the
  `pick` first, from the task and the output of `done` (it names the pick); `verify` also reads the export for the `Area2D`
  (size, centre, `walkable`, `cell`), `masks/solid.png` (the room's size), `room.json` (the mask and the area) and
  `metadata/kiripix_room`. New harness tests: the `extend` steps and the journal, and the area put wrong and then moved.
  The old "owner answers what the agent reports" test used the `pick` entry; it now uses a one-entry fixture of its own.
- **Spec ambiguity:** the ticket says "before `import`", but `extend` needs a picked Source to grow, so the first piece is
  imported by the setup and the join comes before the rest. Also, who `pick`s the joined Variant is not said; `extend done`
  tells the agent to, and the owner fixture doesn't.
- The token count at the gate stays open (the Owner records it with `--milestone m4`).

## Closing notes (2026-11-13)

- The Owner checked the token count at the gate (2026-11-13): fine against M3's.
