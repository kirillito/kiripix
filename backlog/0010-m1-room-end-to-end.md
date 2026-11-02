---
status: todo
milestone: M1
type: spec
---

# M1: a room, end to end (the vertical slice)

Background: [the Kiripix spec](../docs/KIRIPIX_SPEC.md) (§5, §6.1, §8–§11, §14 M1), [the glossary](../GLOSSARY.md)
and [the ADRs](../docs/adr/), especially ADR 0002 (pinned calls), 0003 (the Manifest), 0004 (Runners before the
palette) and 0005 (status is derived). M0 ([0001](0001-m0-skeleton.md)) is done: the Command registry, the JSON
contract, `init`/`new`/`status`/`describe`/`schema`/`next`/`run`, the stage graph, locks, and the palette and quantise
Ops. Use the glossary's words in code, messages and tests.

## Problem Statement

M0 built a tool that behaves the way every Command must, but it can't make anything yet. Every room Stage reports
"not implemented". The owner can't take a single room from an image to Godot, nothing records their Decisions, and
no agent can drive real work. Until one room goes all the way through, nobody knows whether the stage graph, the
Decision journal, pinning, the Manifest and the JSON contract fit together, or whether an agent can actually use them.

## Solution

One room, imported from an image made elsewhere, goes all the way into the Toronto game and walks correctly:
- `brief → source → fit → layers → masks → palette → place → reach → export`, with `layers` a pass-through in M1
  (see Implementation Decisions);
- the owner's input is recorded as Decisions (`set`, `decide`, `override`, `undo`, `redo`, `accept`) in an
  append-only journal, and replayed on every rebuild;
- SAM 2 click-to-segment for Masks, with pinned results and `needs-review` when its input changes;
- Godot export with the Manifest: ownership by hash, `--force`, `--adopt`, and the ID freeze;
- `serve` with REST, SSE progress and Probes, and a React UI for fit, masks, palette, place and the walk test;
- done when a real Toronto room walks correctly in Godot **and** the agent acceptance test passes.

## User Stories

**Decisions**
1. As the owner, I want `kiripix set <id> <stage> key=value…` to set a Stage's parameters, validated against `describe`, so that I tune a Stage without editing TOML.
2. As the owner, I want `kiripix decide <id> <stage> --json '…'` to record a Decision validated against the Stage's Decision schema, so that every click and pick is kept and replayed.
3. As the owner, I want `undo` and `redo` to append entries rather than delete them, so that the journal is never rewritten and merges stay safe.
4. As the owner, I want a merge that left two Decisions with the same parent to put the Stage in `needs-review`, so that the later one never wins silently.
5. As the owner, I want `kiripix override <id> <stage> <png>` to record a hand-painted fix on a Stage's output, so that I can fix what the tool got wrong without editing generated files.
6. As the owner, I want a Stage whose clicks or Overrides were replayed onto changed input to go to `needs-review`, so that a click now landing on a different object is never accepted without me.
7. As the owner, I want `kiripix accept <id> <stage>` to confirm a review and re-record the Decisions against the new input, so that the next replay is exact.
8. As the owner, I want `accept` to refuse unless I'm at an interactive terminal (or the UI with its session token), so that an agent can't accept its own work by mistake.

**The room Recipe**
9. As the owner, I want to write a room's brief (size, mood), and be told when the size isn't a whole number of tiles, so that rooms fit the game's grid.
10. As the owner, I want `kiripix import <id> <file>` to add an image made elsewhere as a Variant, and `pick` to choose the Source, so that my external image tools are a first-class path.
11. As the owner, I want `fit` to detect the Source's pixel grid, or downscale with a mode filter, to the brief's exact size and record the Grid transform, so that the room is at game resolution.
12. As the owner, I want to paint the `solid` Mask by colour flood, brush, or import of a painted image, with an optional cell snap, so that collision is quick to make without ML.
13. As the owner, I want to click an object and have SAM 2 segment it into a Mask, so that complicated shapes take one click.
14. As the owner, I want a SAM 2 result pinned and committed, never silently re-run, so that a rebuild on another machine gives the same Mask.
15. As the owner, I want `run --rerun` to re-run a stale Runner call and land its result in `needs-review`, so that re-running ML is always my explicit choice.
16. As the owner, I want `palette` to map the room to the palette in OKLab, with optional dithering and orphan removal, so that every exported pixel is a palette colour.
17. As the owner, I want to place Exits, Spawns, interactables, lights, emitters and y-sort lines as Markers with stable IDs, so that the game has its gameplay points.
18. As the owner, I want walkable derived from `solid` and the Body's footprint, and Exits and Spawns off walkable ground reported, so that no Marker is unusable.
19. As the owner, I want `reach` to list unreachable Markers, unreachable walkable islands and the narrowest gaps, so that a painted door that can't be reached is caught before Godot.

**Checks and previews**
20. As an AI coding agent, I want `kiripix check <id>` to list every Check's findings with positions and exit with 2 on a failure, so that I know what's wrong and the exact fix.
21. As an AI coding agent, I want `kiripix preview <id> [--stage s] [--overlay masks]` to write a PNG and print its path, so that I see a picture only when I need one.
22. As an AI coding agent, I want `next` to give the exact command for every room Stage, or the owner action when only the owner can act, so that I can drive a room from `import` to `export` without the spec.

**Export**
23. As the owner, I want `kiripix export <id>` to write a Godot 4 scene for the room (Plate, collision from `solid`, navigation from walkable ∩ reachable, Markers, lights, emitter stubs), so that the game instances it directly.
24. As the owner, I want export to write a Manifest file per Asset in the game project and overwrite only files whose hash it recorded, so that my edits in the Godot editor are never lost.
25. As the owner, I want `--force` and `--adopt` to back up the file before overwriting it, and `--dry-run` to list both cases, so that taking a file over is always safe and visible.
26. As the owner, I want exported IDs frozen, so that renaming a Marker never breaks the game's references to it.
27. As the owner, I want Exit pairing checked across rooms (`--all` fails; a single room only warns), so that I can work on a room before its neighbour exists.

**Server and UI**
28. As the owner, I want `kiripix serve` to offer every Command over REST, with progress over SSE and a cancel endpoint, so that a UI can do everything the CLI can.
29. As the owner, I want hover previews of click-to-segment to be fast (the server keeps SAM 2 warm and caches the image embedding), so that segmenting feels interactive.
30. As the owner, I want a status board, a stage bar and stage panels generated from `describe`, with a before/after view for fit and palette, so that I can see and tune a room.
31. As the owner, I want a masks screen with brush, flood and click-to-segment, and `Ctrl+Z`/`Ctrl+Shift+Z` as undo and redo, so that painting collision is quick.
32. As the owner, I want a place screen for Markers and y-sort lines, and a walk test where the Body walks the room with the arrow keys on the real collision, so that I know the room plays before exporting.

**Acceptance**
33. As the owner, I want an agent with no project knowledge to take a room from `import` to `export` using only `--help`, `describe`, `next` and `check`, with my Decisions fed from a fixture file, and its token use recorded, so that "cheaper" is measured.

## Implementation Decisions

**`layers` is a pass-through in M1.** Its run function outputs the fit image unchanged as the Plate, with no
foreground Layers, and needs no owner input. The real `layers` Stage (SAM 2 segment, LaMa inpaint, grow, y-sort
lines) is M2. When it replaces the pass-through, the Stage's input hash changes, so M1 rooms go `stale` from `layers`
down and rebuild through the normal stage graph; no migration is needed. `layer.no_ysort` and
`layers.recompose_mismatch` have nothing to check in M1 and pass.

**`palette` declares `upstream = ["layers"]`**, not `masks`, so a Mask edit doesn't rebuild the palette mapping.
`place` declares both `palette` and `masks` as upstream.

**The Decision journal** (`decisions/<stage>.jsonl`, append-only, LF, `merge=union`):
- Each entry has a ULID `id`, a `parent` (the ID of the entry it followed, or null), the Decision name and its data,
  validated against the Stage's Decision schema.
- Clicks and Overrides also record the hash of the image they were made on.
- `undo` and `redo` append `{undo: <id>}` and `{redo: <id>}`. The current Decisions are the journal replayed in ULID
  order.
- The current Decisions are part of the Stage's input hash.
- Two entries with the same parent put the Stage in `needs-review` with reason "divergent Decisions".
- `set` writes parameters to `asset.toml` (`[stages.<stage>]`), which already has the table for them.

**Replay and review** (§5): an unchanged input means an exact replay and `done`. A changed input with replayed clicks or
Overrides means `needs-review`, which stays derived: any current click or Override whose recorded image hash differs
from the current input means review. Picks replay automatically; a Pick of a deleted Variant means `needs-input`.
`accept` appends re-recorded entries against the new hash and rebases Overrides, so no status is ever stored.

**Owner-only Commands:** `accept` refuses from the CLI unless stdin is a TTY (docs/terminals.md: all three of the
owner's terminals pass), and over REST unless the request carries the session token `serve` gave the browser. It is
never an MCP tool. `KIRIPIX_TEST_OWNER=1` bypasses the check for the test harness only.

**Pinned calls** (ADR 0002): the key covers the input image or crop hash, the click Decisions, the parameters, and the
Runner's ID with a hash of its weights, never the device. Results live in `pinned/`, committed. `run` never re-runs a
Runner; a changed key means `needs-input` with "Runner input changed", and `run --rerun` re-runs it into
`needs-review`. Runner inputs and outputs map through the Grid transform (ADR 0004). CI never downloads weights: tests
use a fake Runner registered through the test hook.

**Export** (§9, ADR 0003): the Manifest lives only in the Godot project under `export.godot.root`, one file per Asset.
Without the game repo at the configured path, export refuses. Godot 4.7 text formats (docs/versions.md).

**`serve`:** a FastAPI adapter generated from the registry, one route per Command, holding no logic (ADR 0006). The
CLI never forwards to a running server.

**The UI is React with TypeScript and Vite** (the owner's decision, 2026-11-02, closing open decision 2 of the spec).
Canvas widgets are plain TypeScript classes mounted by React components through a `ref`, so hover and brush updates
never go through React state. Recorded as ADR 0007 in [0025](0025-m1-ui-shell.md).

## Testing Decisions

- **CLI seam** for every Command and Stage: a temporary Project, `kiripix … --json` as a subprocess, then the JSON,
  the exit code and the files. Journal, replay and owner-only behaviour are tested on the `demo` Kind; room Stages on
  small fixture images.
- **Golden seam** for every new Op (grid detection, downscale, flood, mask split, cell snap, orphan removal,
  walkable, reach, contour and polygon).
- **Contract test:** every new Command has a sample in `tests/cli/test_contract.py`.
- **Export:** against a temporary Godot project folder; the written `.tscn` and Manifest are checked as text. Loading
  them in Godot is part of the gate ([0029](0029-m1-gate.md)), not CI.
- **REST:** the same JSON as the CLI for the same Command, checked through an HTTP client against `serve`.
- **UI:** a few Playwright flows (§12).
- **The agent acceptance test** runs at the gate, not in CI, because it costs money.

## Out of Scope

- The real `layers` Stage, LaMa, grow and foreground Layers (M2). Side-view rooms beyond what the Recipe already
  declares, and side-view reachability (M5).
- `gen`, Providers, the cost ledger (M4). In M1 the Source is always imported.
- The MCP adapter (M4). `export --prune` and the Manifest merge driver (M2).
- Props and characters.

## Further Notes

Tickets [0011](0011-m1-decision-journal.md) to [0029](0029-m1-gate.md). Chains that can run in parallel once their
blockers are done: core (0011–0014, 0023), imaging (0015–0019), ml (0020, 0024), godot (0021, 0022), ui (0025–0027).
