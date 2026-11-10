---
status: todo
milestone: M3
type: spec
---

# M3: characters

Background: [the Kiripix spec](../docs/KIRIPIX_SPEC.md) (§6.3, §7, §8, §9, §11, §14 M3, §16 open decisions 3 and 4),
[the glossary](../GLOSSARY.md) and [the ADRs](../docs/adr/), especially ADR 0002 (pinned calls), 0003 (the Manifest) and 0004
(Runners before the palette, and the character Recipe's order). M2 ([0037](m2/0037-m2-layers-and-props.md)) is done, signed off on
2026-11-07 ([0058](m2/0058-m2-gate.md)). Pinned versions are in [docs/versions.md](../docs/versions.md): Blender 5.2 LTS, Godot 4.7.
Use the glossary's words in code, messages and tests. `model` means only the 3D Model.

## Problem Statement

The game needs characters, NPCs and enemies with many animations in 8 directions, and they must stay on-model. Kiripix
declares the character Kind and its Recipe, but every Stage reports "not implemented until M3": `import` takes only PNG
and JPEG, nothing runs Blender, and export knows only rooms and Props.

The Owner also closed M2 saying the UI is "growing more and more unusable and slow". Those fixes come first.

## Solution

- **First, the M2 fixes** (0078 to 0096, below): status that opens fast, a UI that shows it's working, legible findings,
  a `palette` that doesn't muddy, and the Layer and export fixes.
- **Then the character Recipe, end to end:** `model → rig → clips → render → palette → finish → sheet → export`.
  - A Model is imported as a Variant (`.glb`, `.fbx`, `.blend`) and normalised in headless Blender.
  - `rig` validates a humanoid rig, or guides the Mixamo round trip and picks up the rigged file.
  - `clips` maps named clips to animation sources, with frame range, frame rate and loop flag.
  - `render` runs Blender headless at the target pixel size from a camera preset, 8 directions, toon shaded, no
    anti-aliasing, with colour, normal, depth and object mask passes, subsampled to each clip's frame rate.
  - `palette` maps every frame to one palette for the character. `finish` draws the outline after mapping, in a palette
    colour, and quantises and aligns the normal pass. `sheet` packs an atlas with a fixed pivot at the feet.
  - Export writes `SpriteFrames`, a `CanvasTexture` with the normal map, and an `AnimatedSprite2D` scene.
- **A trial where the spec says "by test":** the outline method (open decision 3). Image-to-3D (open decision 4) is deferred
  to M4 (Q3).
- Done when one character with idle, walk and attack in 8 directions plays in Godot, **and** the agent acceptance test
  passes ([0117](0117-m3-gate.md)).

## User Stories

**The M2 fixes**
1. As the Owner, I want the room list and a room to open in a second or two, so that the UI is usable at 300 rooms.
2. As the Owner, I want every click to show that Kiripix is working, and findings I can read, so that I stop clicking twice.

**Model and rig**
3. As the Owner, I want to import a `.glb`, `.fbx` or `.blend` as a Variant and pick it, so that a bought or hand-made Model is the Source.
4. As the Owner, I want the Model's scale and up axis normalised, so that every character renders at the same height in pixels.
5. As the Owner, I want a humanoid rig checked, and when there's none, the Mixamo steps shown and the rigged file picked up, so that the round trip needs no guesswork.

**Clips and render**
6. As the Owner, I want to name clips (`idle`, `walk`, `attack`…) with their source, frame range, frame rate and loop flag, so that the game's animation names are mine and stable.
7. As the Owner, I want a camera preset tuned once per Project and reused by every character, so that all characters share one angle and light.
8. As the Owner, I want 8 directions rendered at the target size with no anti-aliasing and toon shading, so that the frames read as pixel art before any clean-up.
9. As the Owner, I want renders to take the GPU lock and to be cancellable between frames, so that Blender and the Runners never fight over 8 GB.

**Palette, finish and sheet**
10. As the Owner, I want one palette per character across all its frames, so that it doesn't flicker between frames.
11. As the Owner, I want an outline in a palette colour that is consistent from frame to frame, so that the character reads on any room.
12. As the Owner, I want a normal map the same size as the colour frames, so that 2D lights in Godot light the character.
13. As the Owner, I want the feet fixed at the pivot, with a Check when they drift in a stationary clip, so that an idle character doesn't swim.

**Export and UI**
14. As the Owner, I want `SpriteFrames`, a `CanvasTexture` and an `AnimatedSprite2D` scene with frozen clip IDs, so that the game instances the character and refers to its animations by name.
15. As the Owner, I want a frame strip with onion skin, a direction picker and a clip player at game speed, so that I judge an animation without opening Godot.

**Measures**
16. As the Owner, I want the agent acceptance test to take a character to export too, with its tokens recorded against M2's, so that "cheaper" stays measured.
17. As the Owner, I want my time per character recorded at the gate, as time per room is, so that "faster" is measured for characters too.

## Implementation Decisions

**Blender runs as a separate process** (spec §12): `blender -b -P kiripix/blender/<script>.py -- <args>`, with arguments and
results as JSON files. Only scripts in `kiripix/blender/` import `bpy`, and nothing in Kiripix imports them. Blender is found
through a Project setting or `PATH`, and a version other than 5.2 is a finding, not a guess.

**Blender is replaceable in tests, as a Runner is.** A Stage reaches Blender through one seam, so the test harness swaps in a
fake renderer through `KIRIPIX_TEST_RECIPES`, as it swaps in fake Runners. CI has no Blender and never renders.

**Blender is not a Runner** (the glossary: a Runner is an ML model), **and its renders aren't pinned** (Q1). `render` is
deterministic work, rebuilt like any other Stage. The Blender version and the render settings are among its inputs, so an
upgrade shows `render` as out of date and the Owner rebuilds when they choose. A change can't reach the game unseen: export
writes into the game repo, where the Owner reviews the diff. [0098](0098-m3-blender-renders-and-pinning.md) records this as
an ADR before any Stage that runs Blender is built.

**Outlines are drawn in `finish`, after `palette`, in a palette colour** (ADR 0004), **as a 1 px silhouette from the
render's object mask** (Q2). The mask is exact and binary, so the line has no isolated pixels and stays still on still parts.
In-render methods (inverted hull, Freestyle) size lines in scene units, which at 52 px come out 0 to 2 px and flicker. The
trial [0106](0106-m3-outline-method-trial.md) confirms the silhouette on a real character.

**Names** (Q5). Clip IDs are lowercase snake_case verbs as the game sees them: `idle`, `walk`, `run`, `attack`, `hit`, `ko`,
`interact`. A variant gets a name for what it is (`attack_kick`), not a number. Directions are compass suffixes from the
screen's view, `s sw w nw n ne e se`, with `s` facing the camera. A `SpriteFrames` animation is `<clip>_<dir>`, such as
`walk_sw`: the direction is always the last `_` segment, so a clip ID may contain `_`. The 8 suffixes are frozen once per
Project; a clip's ID is frozen at its first export.

**Clip IDs are frozen once exported** (ADR 0003). The Manifest's exported IDs gain `clips`, which bumps its schema.

**Character height gets a setting** (spec §16, decision 1: 52 px in the Toronto RPG, with "no setting until the character
recipe (M3) adds one"). [0099](0099-m3-core-for-characters.md) adds it.

**Time per character is a measure,** beside time per room. There is no baseline: the gate sets the first data point. It
records the character's journal span and the Owner's own total, with the Mixamo round trip and the render time noted
apart, since they are waiting rather than work.

**No new dependency without `uv.lock`.** Blender is an external tool, pinned in `docs/versions.md`, not a Python dependency.

## Questions for the Owner

Not decided here. A ticket that depends on one says so, and stops until it's answered.

| # | Question | Where it matters |
|---|---|---|
| Q1 | **Answered 2026-11-07: not pinned.** A render is deterministic work, with the Blender version and render settings among its inputs (above). | [0098](0098-m3-blender-renders-and-pinning.md), every Stage that runs Blender |
| Q2 | **Answered 2026-11-07: a 1 px silhouette from the object mask,** in `finish` after `palette` (above). Inverted hull only if the Owner dislikes it in 0106; Freestyle isn't tried. | [0106](0106-m3-outline-method-trial.md) |
| Q3 | **Answered 2026-11-07: deferred to M4.** The Owner's rule was M3 only if under 1M tokens; the estimate was 0.7 to 1.2M, and the models that fit 8 GB rig badly. The trial is now [0144](m5/0144-m5-image-to-3d-trial.md), in M5, beside Providers (moved from M4 on 2026-11-08). | 0144 |
| Q4 | **Answered 2026-11-07: a Quaternius character (CC0),** not a blocky or toy-like one. Its base body and outfit are separate meshes on one skeleton, so they are joined into one `.blend` in Blender first; that file is the Model Kiripix imports. Upload it to Mixamo once first to check that it rigs cleanly. Which character and outfit is still the Owner's pick. | the gate, 0106 |
| Q5 | **Answered 2026-11-07:** snake_case verbs (`attack`, not `attack_1`) and `<clip>_<dir>` with compass suffixes (above). | 0103, 0104, 0113 |
| Q6 | **Answered 2026-11-07: all 8 directions are rendered,** none mirrored, so an asymmetric character stays right. | 0104 |
| Q7 | **Answered 2026-11-08:** presets are settings in `[character]` in `kiripix.toml`, picked by name by an Asset's `camera` parameter. M3 ships only `top34_8`, at a 30° elevation; `side` and `battle` wait until needed. | 0099, 0104 |
| Q8 | **Answered 2026-11-08:** `height = 52` in `[character]` is the Project default, and a character's `height` parameter overrides it. | 0099 |
| Q9 | **Answered 2026-11-08:** a `colors` parameter on the character's `palette` Stage, default 16; `palette_subset` picks the n best-fitting palette colours in OKLab across all frames. | 0107, 0110 |
| Q10 | **Answered 2026-11-08:** the ground point under the root that Blender reports per frame, so no `feet_point` Op; the Check reads the pivots it's given. Stationary clips carry a `stationary` flag on the `clip` Decision (default false); only those are checked. | 0103, 0108, 0112 |
| Q11 | Rigify for non-humanoids: in M3, or deferred until a non-humanoid character is needed? | 0102 |
| Q12 | **Answered 2026-11-08:** one atlas per character, with one cell size for the whole character. | 0108, 0112 |

## Testing Decisions

- **CLI seam** for every Stage and Command, on a fake renderer from `tests/fixtures/kiripix_test_recipes.py` that writes fixed
  frames. It checks status, Decisions, findings, exit codes and the files.
- **Golden seam** for every new Op: the palette subset across frames, normal quantise and encode, the outline, atlas
  packing, the feet point.
- **A real Blender render** is a marked test (`blender`), skipped when Blender 5.2 isn't found, on a tiny fixture Model made
  by a committed script ([0100](0100-m3-character-test-fixtures.md)). It checks sizes, passes and frame counts, not pixels,
  since renders aren't pinned (Q1) and aren't bit-exact across machines.
- **Export:** `.tres` and `.tscn` checked as text against a temporary Godot folder. Opening them in real Godot is the gate's.
- **Contract test:** every new or changed Command has a sample in `tests/cli/test_contract.py`.
- **UI:** a few Playwright flows per screen, on the fake renderer.
- **The agent acceptance test** runs at the gate, not in CI.

## Out of Scope

- Room Looks (M4, ADR 0009). Providers, `gen`, MCP, and image-to-3D, local or as a Provider (M4).
- Side-view rooms, parallax and platform reachability (M5).
- Animation authoring (a non-goal): clips come from Blender or Mixamo.
- Dash: it stays dormant at `dash = 0`.
- Portraits, VFX sheets and tilesets (later).

## Further Notes

Child tickets: [0098](0098-m3-blender-renders-and-pinning.md) to [0116](0116-m3-agent-acceptance-test.md), and the gate
[0117](0117-m3-gate.md).

**The first wave: the M2 fixes,** before any character work, at the Owner's request. In order:

| Wave | Tickets |
|---|---|
| 1a | [0090](0090-m3-status-without-re-deriving-lifts.md) first: it slows every screen |
| 1b | [0083](0083-m3-ui-show-that-work-is-happening.md), [0093](0093-m3-ui-findings-a-person-can-read.md), [0094](0094-m3-palette-stage-muddies-rooms.md), [0095](0095-m3-matting-result-changes-after-accept.md), [0096](0096-m3-merge-exported-images.md), [0091](0091-m3-remove-a-layer.md), [0081](0081-m3-downscale-keeps-one-scale.md), [0088](0088-m3-check-says-what-is-out-of-date.md) |
| 1c | [0092](0092-m3-ui-layer-screen-legible.md), [0082](0082-m3-ui-canvas-navigation.md), [0089](0089-m3-time-a-lift-honestly.md), [0084](0084-m3-layer-stats-probe.md), [0085](0085-m3-click-preview-probe.md), [0086](0086-m3-preview-layers-and-brighten.md), [0087](0087-m3-layer-clean-up.md), [0079](0079-m3-segment-with-a-box.md) |
| 1d | [0080](0080-m3-ui-polygon-tool.md), and [0078](0078-m3-reach-probe.md) last: it closes itself if no first pass uses clicks |

**The character work:**

| Wave | Tickets |
|---|---|
| 0 | 0098 may run during the first wave: it touches no code |
| 2 | 0099, 0100, 0107, 0108 |
| 3 | 0101 |
| 4 | 0102 |
| 5 | 0103, 0114 |
| 6 | 0104 |
| 7 | 0105, 0110; 0126 (core hook), then 0119; 0120, 0121, 0122 (found in 0104 and 0114, added 2026-11-09); 0123 and 0124 alongside |
| 8 | 0106 (the trial), then 0109; 0125 once 0122 to 0124 are done |
| 9 | 0111 |
| 10 | 0112, then 0115 (after 0125) |
| 11 | 0113 |
| 12 | 0116 |
| 13 | 0117, the gate |

**Don't run these at the same time, because they edit the same files:**
- The UI tickets 0080, 0082, 0083, 0092, 0093, 0114, 0125 and 0115 (`web/src/App.tsx` and the canvas).
- 0101 to 0105, 0110 to 0112, 0119 and 0120 to 0122 (`kiripix/recipes/character.py` and `kiripix/blender/`).
- 0123 and 0103's `read_actions.py`: 0123 extends it, so not alongside a ticket that changes `clips`.
- 0107, 0108 and 0109 (`kiripix/ops/__init__.py`).
- 0096 and 0113 (`kiripix/export/`).
