---
status: todo
milestone: M1
agent: imaging-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0016-m1-masks.md, 0017-m1-palette-stage.md]
---

# M1: place, and walkable

Spec §6.1 (place), §7 (reach: walkable) and the glossary (Marker, Exit, Spawn, Body, Walkable, Y-sort line). User
stories 17 and 18 of [0010](0010-m1-room-end-to-end.md).

## What to build

- Op (`reach`): walkable from `solid` and the Body's footprint (where the footprint fits without touching solid).
  Pure, golden-tested.
- The room's `place` Stage, with upstream `palette` and `masks` and input `body`: replays `marker` Decisions into a
  Markers file (ID, type, position, and per-type fields: an Exit's target room and Exit ID; a light's colour, radius
  and energy; an emitter's name; a y-sort line's end points). Extend the `marker` Decision schema for these fields.
  `undo` removes a Marker, and a new `marker` with the same ID moves it. Also outputs walkable as a derived Mask.
- Checks: `marker.duplicate_id`; `marker.not_walkable` (Exits and Spawns), with the position; `layer.no_ysort`, which
  passes with no foreground Layers in M1.
- Changing `[body]` re-derives walkable cheaply and makes `place` `stale`.

## Acceptance criteria

- [ ] Golden tests: walkable for a 12×8 footprint around a corner, and through a gap narrower than the footprint.
- [ ] A Spawn placed on solid reports `marker.not_walkable` with its position, and `check` exits 2.
- [ ] Moving a Marker (same ID) leaves one Marker, at the new position.
