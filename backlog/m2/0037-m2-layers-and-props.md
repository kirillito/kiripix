---
status: done
milestone: M2
type: spec
---

# M2: layers and props

Background: [the Kiripix spec](../../docs/KIRIPIX_SPEC.md) (§5, §6.1, §6.2, §7–§11, §14 M2), [the glossary](../../GLOSSARY.md)
and [the ADRs](../../docs/adr/), especially ADR 0001 (binary Masks), 0002 (pinned calls), 0003 (the Manifest) and 0004
(Runners before the palette). M1 ([0010](../m1/0010-m1-room-end-to-end.md)) is done, signed off on 2026-11-04. Use the
glossary's words in code, messages and tests.

## Problem Statement

A room reaches Godot as one flat Plate, so an actor can never walk behind a lamp post. `layers` is still M1's
pass-through. The owner can't make a Prop at all: every prop Stage reports "not implemented until M2". A deleted Asset's
files stay in the game forever, and two game branches that export the same Asset conflict with no way to resolve it.

## Solution

- `layers` becomes real: click objects to lift them out (a Runner segments, a Runner inpaints the hole), or take them
  from the difference between a Plate image and the full image, with `grow`, the Derived mask `foreground` and y-sort
  lines. M1 rooms rebuild from `layers` down through the normal stage graph, with no migration.
- `palette` maps the whole composite once, and Plate and Layers still recompose exactly.
- The room's scene gets foreground `Sprite2D`s, y-sorted or flagged "always above".
- The prop Recipe works end to end, with chroma key or matting, and exports a scene.
- `export --prune`, and the Manifest merge driver with `manifest repair`.
- The Owner spends less time per room, and M2 measures it: click-to-segment timed and fixed, a one-click room border,
  flood that works on painted art, and a trial of Claude doing the first pass.
- Done when a real room with a lifted Layer and real Props behave correctly in Godot **and** the agent acceptance test
  passes ([0058](0058-m2-gate.md)).

## User Stories

**Layers**
1. As the owner, I want to click an object and have it lifted into a named foreground Layer with the Plate filled behind it, so that actors can walk behind it.
2. As the owner, I want negative clicks to refine a Layer, and hover previews as on the masks screen, so that a lift takes few clicks.
3. As the owner, I want segmentation and inpainting pinned, never silently re-run, and to land in `needs-review`, so that a rebuild on another machine gives the same Plate.
4. As the owner, I want `grow` to widen a Layer's alpha and its Plate hole together, so that no background rim is left on the Plate.
5. As the owner, I want to trim a leftover rim from a Layer by hand, so that one bad edge doesn't mean a re-run.
6. As the owner, I want to supply a Plate image alongside the full image and get Layers from their difference, so that a generated plate plus props needs no ML.
7. As the owner, I want Plate and Layers checked to recompose exactly, before and after `palette`, so that lifting never changes the picture.
8. As the owner, I want a room with no foreground objects to need nothing extra, so that M1 rooms just rebuild.

**Y-sort**
9. As the owner, I want a y-sort line or an "always above" flag on every foreground Layer, with a Check when one is missing, so that draw order is never left to chance.
10. As the owner, I want the walk test to draw Layers by those lines, so that I see the order before exporting.

**Props**
11. As the owner, I want a prop's background removed by exact chroma key or by matting, on the full-size Source, so that both flat and painted Sources work.
12. As the owner, I want fit, palette and an optional 1 px outline to behave as for rooms, with binary alpha, so that props match the game's look.
13. As the owner, I want to draw a prop's footprint and origin, and get a scene with collision and that origin, so that the game instances it directly.

**Export**
14. As the owner, I want foreground Layers in the room's scene with frozen IDs, so that the game can refer to them.
15. As the owner, I want `export --prune` to remove a deleted Asset's files under the hash rule, so that the game doesn't collect dead files and its edits are safe.
16. As the owner, I want a git merge driver for the Manifest, and `manifest repair` for a conflict on GitHub, so that two branches exporting one Asset don't block me.

**Acceptance**
17. As the owner, I want the agent acceptance test to lift a Layer too, with its token use recorded against M1's, so that "cheaper" stays measured.

**Time per room**
18. As the owner, I want one action that walls off a room's edges, side by side, so that I don't trace them with a brush.
19. As the owner, I want click-to-segment fast after a rebuild, not only on the first hover, so that clicking stays fluid.
20. As the owner, I want the time per room recorded at each gate, so that "faster" is measured as "cheaper" is.
21. As the owner, I want to see how far a Claude first pass gets on a real room, so that I know whether to plan around it.

## Implementation Decisions

**Runners stay replaceable** (spec §8). A Stage names a Runner only through a role constant in `kiripix/runners/__init__.py`,
as `SEGMENTER` does today: new ones are `INPAINTER` and `MATTER`. Only a Runner's own file knows its engine. Decisions are
in target pixels, never in a Runner's terms. Swapping one sends its pinned calls to "Runner input changed", and
`run --rerun --all` remakes them for review.

**A Layer's identity is its ID,** given by the Decision that lifts it, and frozen once exported (ADR 0003). `plate` is
reserved. Layer files sit flat in the Stage's folder as `layer.<id>.png`, because `show` lists only top-level files.

**Recompose by construction.** Layer pixels are the fit image cut by alpha, the hole equals the union of the alphas, and
Plate pixels outside the hole are the fit image's. An Override on `layers` may paint inside a hole, to fix an inpaint.
Painted outside one, it fails `layers.recompose_mismatch`, whose `owner_action` says to paint on `fit` instead.

**M1 rooms need no migration.** `layers` gains parameters, so its input hash changes and M1 rooms go stale from there
down. With no layer Decisions, `plate.png` stays byte-identical to `fit.png`, so Mask Decisions don't go to `needs-review`.
A re-export writes nothing and leaves the counter alone.

**Time per room is a measure,** beside the acceptance test's tokens. The M1 baseline, from `room.harbor_front`'s journal: 13.4
minutes of real work on a rough pass, the Owner's first time with the tool (24 clicks, 7 floods, 1 brush stroke, 5 Markers).
The journal's whole span is 19.1 minutes, but its first 5.5 went on learning the tool and were then undone, so the span
overstates the work and the undos aren't corrections. The span leaves out time before and after it, so the Owner's own total
is recorded beside it. Their estimate for a fully polished small room is a couple of hours.

**No new dependency without `uv.lock`.** OpenCV and scikit-image are in the spec's stack but aren't dependencies today;
write Ops in numpy unless a ticket says otherwise.

## Decisions

The Owner took these on 2026-11-04. The spec and ADRs follow them.

| # | Question | Decision |
|---|---|---|
| D1 | How is a rim trimmed? | A `trim` Decision: a brush in target pixels on one Layer's alpha, `on_image`, giving those pixels back to the Plate. ADR 0004 is amended. |
| D2 | What is "partial" alpha? | A target pixel whose Source cell is partly covered by the Runner's Mask, or has alpha strictly between 0 and 255. It works for any Runner. |
| D3 | Sloped y-sort lines | Sort at the line's mean y, rounded, with a warning if the ends differ by more than half a tile. |
| D4 | `layers` with no Decisions | `done`, with no owner input. |
| D5 | Difference to Layers | The Owner names a Layer with one click in a connected region. Unclicked regions stay in the Plate. No automatic Layers. |
| D6 | Flood tolerance | Compare against the clicked pixel, not neighbour to neighbour. Range 0-0.2 in OKLab distance. The UI's default of 0.04 is a starting guess: confirm it on `harbor_front`'s 16 recorded points, aiming near the palette-mapped fills (up to 3,009 px). CLI and agents stay at 0 when it's left out. |
| D7 | Chroma key exactness | Exact. A finding when the key removes almost nothing, or leaves a fringe of near-key pixels, points to `method=matting`. A tolerance only if a real prop needs one. |
| D8 | A prop's size limits | Exactly the brief's size, and no larger than `project.resolution`. |
| D9 | Prop foreground split | Deferred. Y-sort at the origin handles a lamp's head; only arch-like props need a split. |
| D10 | GPU lock through a Stage's run | `gpu=False` on `layers` and `cutout`: Runner calls take the lock themselves. [0059](0059-m2-slow-click-to-segment.md) tests the same for `masks`. |
| D11 | The `--prune` surface | Alone: prunes every deleted Asset and exports nothing. With `--all`: exports, then prunes. With `<id>`: prunes that deleted Asset, and refuses if the Asset exists. |
| D12 | A merged Manifest's `files` | Ours in `files`, theirs in the existing `replacing` map, so the next export accepts either. No schema bump. |
| D13 | Installing the driver | A new `kiripix manifest install`. `.gitattributes` under `<root>/manifest/`. The local git config uses the current interpreter's full path (`python -m kiripix`). |
| D14 | What `repair` covers | Only a Manifest with conflict markers, by the same rule. A clean Manifest with wrong hashes stays with export's refusal and `--force`. |
| D15 | `LightOccluder2D` | Not in M2. |
| D16 | Acceptance test Runners | Fake ones, set by the harness only, on a room only. The gate proves the real Runners. Check whether the test Kind `demo` showing in `describe` skews the run. |

## Testing Decisions

- **CLI seam** for every Command and Stage. Layer and prop tests use fake Runners from
  `tests/fixtures/kiripix_test_recipes.py`, on small fixture images. CI never downloads weights.
- **Golden seam** for every new Op: difference Mask, grow where partial, recompose, cut, chroma key, outline.
- **Contract test:** every new Command has a sample in `tests/cli/test_contract.py`.
- **Export:** the `.tscn` and Manifest checked as text against a temporary Godot folder; real Godot is the gate's.
- **Merge driver:** a real `git merge` in a temporary repo.
- **UI:** a few Playwright flows.
- **The agent acceptance test** runs at the gate, not in CI.

## Out of Scope

- Side-view parallax, depth and platform reachability (M5). Characters (M3). `gen`, Providers, edit-API inpainting, MCP (M4).
- Dash: it stays dormant at `dash = 0`. No ticket invests in it.
- "Promote to Prop", placing Props in a Room. The prop foreground split (D9) and `LightOccluder2D` (D15).
- Building multi-screen rooms: an open decision, spec §16, which [0063](0063-m2-multi-screen-source-trial.md) tests. The room
  border (0060) takes sides, so it doesn't close that off.

## Further Notes

Tickets [0035](0035-m2-ui-brush-stroke-slows-down.md), [0036](0036-m2-flood-does-nothing-on-a-painted-plate.md) and
[0038](0038-m2-core-for-layers.md) to [0063](0063-m2-multi-screen-source-trial.md). Lights and emitters were built in M1
([0021](../m1/0021-m1-room-export-and-manifest.md)); M2 only proves them in Godot, at the gate.

**Order:**

| Wave | Tickets |
|---|---|
| 1 | 0059 (first), then 0035, 0036, 0038, 0039, 0041, 0042, 0048 |
| 2 | 0040, 0049, 0050, 0055, 0060 |
| 3 | 0043, 0051, 0061 |
| 4 | 0044, 0045, 0046, 0056, 0062 |
| 5 | 0047, 0053, 0054 |
| 6 | 0052, 0057 |
| 7 | 0058, the gate |

0063 is the Owner's and blocks nothing until the gate. Do its SAM 2 clicks after 0059, so they measure the fixed timing.

**Don't run these at the same time, because they edit the same files:**
- 0047, 0048, 0049 and 0052 (`kiripix/export/__init__.py`, `commands/export.py`).
- 0036, 0043, 0044, 0045, 0046, 0059 and 0060 (`recipes/room.py`). 0050 moves shared code out of that file, so it goes
  before 0043 or after 0046.
- 0035, 0055 and 0061 (the masks screen).
