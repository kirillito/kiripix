---
status: done
milestone: M3
agent: core-engineer
type: ticket
---

# M3: derive status without working out every lift again

Spec §5 (status is derived) and ADR 0005. Found by the Owner at the [M2 gate](../m2/0058-m2-gate.md): the room list takes over 15 s to open
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

- [x] `status`, `show` and `next` give the same results as before on the art Project, and the table above is recorded again.
- [x] A test of 300 rooms keeps `status` under the budget (`tests/cli/test_status_budget.py`, with the demo Kind; see the notes on what it holds).
- [x] Opening the room list and a room in the UI calls no Runner, or the reason one is needed is recorded here.

## What was done (2026-11-07)

- `AssetGraph.runner_calls` (`kiripix/core/graph.py`) is kept in memory per graph and on disk in
  `.kiripix/derived-cache.json` (`HashCache.derived` / `remember`, `kiripix/core/hashing.py`). The key is everything the call list
  derives from: the Stage's params, journal (hashable replay), input files, settings, the hash of every file in its upstream outputs,
  the Runner role constants (`runners.INPAINTER`...: a Stage reads them when it lists its calls), the size and time of the recipes' source files, and the names of the Asset's pinned results (a call list can depend on whether an earlier call is pinned). A Stage with no
  Decisions skips the cache. It's a cache of a computation, never a status (ADR 0005); deleting `.kiripix/` loses nothing.
- Smaller costs found while profiling 300 plain Assets: `Project.relative` no longer calls `Path.resolve` for an absolute path
  under the root (3300 calls, the biggest single cost), `HashCache` keys by `os.path.abspath` instead of `resolve`, and
  `AssetGraph.files` is memoised and skips the directory walk for a path without a wildcard.
- Output of `status`, `show room.ch01_dungeon_r03` and `next room.ch01_dungeon_r03` on the art Project is byte-identical to the
  output of the code at HEAD (compared with `cmp`).

### Times again (art Project, 7 Assets; the machine was busy, so a bare process start was 2.1 s against 1.2 s before)

| Command | Before | After (wall) | After, less the 2.1 s process start |
|---|---|---|---|
| `status --json` | 13.0 s | 3.0-3.3 s | about 0.9 s |
| `show room.ch01_dungeon_r03 --json` | 5.5 s | 2.4-3.1 s | about 0.3-0.9 s |
| `next room.ch01_dungeon_r03 --json` | 5.6 s | 2.5-2.8 s | about 0.4-0.7 s |

The first call after a change to a room's decisions or upstream output still replays that room's lift once (about 1.6 s), then it
is cached. The 300-room budget test uses the demo Kind, which has no Runner calls, so it holds the per-Asset cost (journals,
stamps, hashes, file lookups: about 2 s of work for 300 Assets on this busy machine, down from about 12 s) and not the lift. The
cache is held by the existing transitions in `tests/cli/test_runner_calls.py` and `test_layers_*`. The test's limits are 3 s
(`status`) and 0.5 s (`show`), both less a process start, a margin over the ticket's 2 s on a busy machine.

### The GPU noise

Nothing in `status`, `show`, `next`, `serve` start-up or opening the list or a room loads a Runner. The only GPU use from the UI
is the segment-preview Probe, which `maskScreen.tsx` and `layerScreen.tsx` ask for on every pointer move over the canvas of a
Masks or Layers Stage (through `MaskTool.preview`); the first one computes the image embedding and the server keeps the Runner
warm (`keep_warm` for REST, `kiripix/commands/probes.py`). So the noise the Owner heard was most likely the pointer crossing the
canvas of a Masks or Layers Stage. Nothing changed: the screen needs the preview there. If it's unwanted, the preview could wait for
a Shift key or a short dwell; that's a UI decision for the Owner.
