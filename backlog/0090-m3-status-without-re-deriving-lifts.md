---
status: todo
milestone: M3
agent: core-engineer
type: ticket
---

# M3: derive status without working out every lift again

Spec §5 (status is derived) and ADR 0005. Found by the Owner at the [M2 gate](m2/0058-m2-gate.md): the room list takes over 15 s to open
and a room about 13 s, with nothing on screen, in a Project of 6 rooms and 1 Prop. "How long will it take with 300 rooms?"

## What was measured (2026-11-07)

From the CLI in the art Project, with no UI and no `serve`:

| Command | Wall time |
|---|---|
| `status --json` (7 Assets) | 13.0 s |
| `show room.ch01_dungeon_r03 --json` | 5.5 s |
| `next room.ch01_dungeon_r03 --json` | 5.6 s |
| `import kiripix.commands` alone | 1.2 s |

A profile of `status`: 10.7 s of 11.5 s is in `LayersStage.runner_calls` (`kiripix/recipes/layers.py:332`), through `_lift`
(`layers.py:274`). To find which Runner calls a Stage needs, the graph replays each room's lift: `partial_cells`,
`mask_to_source`, `connected_regions` and `hole_params`, for every room with Layers, on every call, from
`graph.runner_calls` (`kiripix/core/graph.py:239`) by way of `missing_calls`, `unreviewed_pins` and `input_hash`. About 1.6 s per
room with Layers, so 300 such rooms would take about 8 minutes. The UI calls `status`, `show` and `next` on every refresh, so
every action in it pays this too.

No Runner is loaded during `status`. The GPU noise the Owner heard while the list opened comes from something else, and isn't
explained yet.

## What to do

1. **Make the Runner calls a Stage needs cheap to ask for.** Its own decisions decide them, so cache them by what they're derived
   from (the Stage's input hash and its journal), or keep the derivation in the Stage's built output. Status stays derived and is
   never stored (ADR 0005); this caches a computation, not a status.
2. **Find what uses the GPU when the UI opens the list or a room,** for example a warm Runner loading or an embedding computed on
   open, and stop it unless the screen needs it.
3. **Record the times above again** after the change, and set a budget the tests can hold: `status` on a Project of 300 rooms with
   Layers (the test Kind `demo` can stand in) in under 2 s, and `show` for one room in under 0.5 s.

## Acceptance criteria

- [ ] `status`, `show` and `next` give the same results as before on the art Project, and the table above is recorded again.
- [ ] A test of 300 rooms keeps `status` under the budget.
- [ ] Opening the room list and a room in the UI calls no Runner, or the reason one is needed is recorded here.
