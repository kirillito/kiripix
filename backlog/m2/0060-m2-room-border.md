---
status: done
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: wall off a room's edges in one Decision

Spec §6.1 (masks). Story 18 of [0037](0037-m2-layers-and-props.md). Found by the Owner at the M1 gate: they traced the room's
edges by hand with the brush, relying on the stroke sticking to the edge as the pointer left the image.

## The gap

The walk test can't leave the room, because `walkable` needs the footprint wholly inside it. The exported scene has no wall at
the edge, only the shapes from `solid`, so without one painted the Body walks out of the room in Godot.

## What to build

- A `border` Decision on `masks`: `{mask, sides, thickness}`. `sides` is any of `top`, `right`, `bottom` and `left`. It isn't
  `on_image`, because it depends only on the room's size, so a changed Plate doesn't put it in `needs-review`.
- It replays in journal order with the other Decisions, so a later brush erase can open a gap in it. A wall needs no gap for an
  Exit: an Exit stands on walkable ground inside the wall, and the game triggers it there.
- `thickness` defaults to a value that survives export: at the `export` Stage's default `tolerance`, simplifying must not
  collapse the wall. Choose it by test, and state it in `describe`.
- An info finding, `masks.open_edge`, when walkable ground touches a room edge with no wall, whose `fix` is the exact `decide`
  command. Info, since an open side can be intended.

## Why a Decision and not automatic

It stays visible, undoable and replayed like any other edit, and a side can stay open, which a multi-screen room may need
(spec §16). An agent gets it from the finding's `fix`.

## Acceptance criteria

- [x] `decide` with all four sides, then `run`: `solid` covers the edges, and the exported scene's collision has the wall.
- [x] With `sides` of `left` and `right` only, the top and bottom stay open and `masks.open_edge` names them.
- [x] `undo` removes the wall. A later brush erase opens a gap in it.
- [x] A changed Plate doesn't send a `border`-only `masks` to `needs-review`.
- [x] A golden test of the Op on a small room, including a thickness larger than a side.
- [x] `describe room` documents the Decision.

## Built

Default `thickness` 2 (a wall of 1 also survives at tolerance 1; golden test). The export scene's collision comes from
`solid` unchanged, so a border in `solid` is in it; the golden test checks the simplified shapes keep every wall pixel.
`masks.open_edge` is silent while neither `solid` nor `pit` is painted (`mask.none_painted` says so already).
