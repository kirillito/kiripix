---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0152-m5-character-layers.md
depends_on: [0290-m5-wearable-kind.md]
---

# M5: a Wearable's `model`, `rig` and `render`, with the body as holdout

Part of [0152](0152-m5-character-layers.md). From the trial [0153](0153-m5-character-layer-trial.md)'s Results and the Owner's answers (2026-11-18).

## What to build

- **`model` and `rig`:** import the Wearable's meshes (a GLB or FBX of the parts only, on the body's skeleton); `rig` checks them
  against the body's rig by bone names, with a finding naming missing bones. Material names are kept per Wearable, numbered after
  the body's in the material pass.
- **`render`:** the body's clips, camera preset, directions, frames, cell and pivot, with the body's meshes in the scene as a
  **holdout** (they hide what's behind them but aren't drawn). The trial's wrapper (`backlog/m5/0153-trial/render_layers.py`)
  added `show` and `holdout` to `render_frames.py` from outside: build that into it.
- **Passes per Wearable:** colour, alpha, material, **depth** and **normal**, as the body's, so the game can stack by depth (in the
  trial, 1 px and 7 px wrong, against 1.5-2 % stacked by a fixed order).
- Record the render seconds per Wearable in `render.json`: the game budgets each hair style and outfit by it.

## Acceptance criteria

- [x] Fake Blender at the CLI seam: a Wearable renders the body's clip names and frame counts, with the holdout passed through.
- [x] A `blender`-marked test on 0281's Model: a Wearable's alpha is empty where the body is in front of it, and body + Wearable
      stacked by depth match a full render of both within a few px.
- [x] A change to `render`'s outputs bumps its `version`, named in the Result.

## Result

- **`model`** (`wearable_render.run_wearable_model`): the character's `model` with `normalise_model.py`'s new `like` argument, the
  body's `model.blend`. The Wearable's meshes are turned, scaled and moved by the body's own `model_root`, never by their own
  height (a hat is not 1.7 m): the same place as the body, so the Wearable's file must be in the body's source space. `facing` is
  not a Wearable parameter (the body's holds). `model` waits for the body's `model`.
- **`rig`**: the Wearable's armature against the body's `rig.json` by bone name, through `validate_rig`: a bone the Wearable lacks,
  a bone it adds, or a bone under another parent is `wearable.rig_mismatch` (owner_action, naming the bones), because the body's
  armature drives the Wearable's meshes. Writes `rig.json` (the bones and their parents).
- **`render`** (`wearable_render.run_wearable_render`, and `render_frames.py`'s new `wearable` argument, built in from the trial's
  `render_layers.py`): the body's `model.blend` is opened, the Wearable's skinned meshes are brought in and re-pointed at the
  body's armature (their Armature modifiers and parent), the scene is set up with the body alone (so the camera, ground point and
  depth range are the body's own, checked against the body's `render.json`), then the body is a holdout (pass index 0, so it is
  outside the object mask) and the Wearable renders. Clips, directions, camera, frame, pivot, `px_per_unit`, toon: read from the
  body's built `clips.json`, `render.json` and `model.json`. Passes: colour, normal, depth, mask, material, as the body's (alpha is
  the colour's and the mask). The Wearable's materials are numbered after the body's (`materials` in its `render.json` are its own,
  from index body count + 1; `body.materials` is the count). A material that has the name of one of the body's gets Blender's
  `.001`. No per-clip reuse: a Wearable renders whole.
- **Cost in `render.json`:** `seconds` = `{measure, render, frames, per_frame}` (Blender wall seconds). On 0281's fixture, 32 frames at
  96 px on the CPU: about 4.6 s, 0.14 s a frame (machine shared with other tests).
- **The wait:** new `BodyInputs.wait` and `StageRun.body` (`BodyView`: the body's output folders for the Stages named for its Kind, and
  its source files, the clip sources of it and its base); core (`graph._body_view`, `_body_not_built`) makes a Wearable's `model`,
  `rig` and `render` needs-input while a Stage of the body they read isn't `done` (stale counts), with `its body character.zed has no
  built render (it is needs-input)` and the command `kiripix run character.zed render`. The test Kind `demo_wearable` sets `wait` off.
- **`wearable.outside_cell` fires** (`check_wearable_render`): `render` measures the Wearable's own extents per frame (the `measure`
  mode of `render_frames.py` with the body hidden), records the frames that don't fit the body's cell (`outside_cell`: clip,
  direction, frame) and `margin`, and the Check names up to 6 of them with the fix `kiripix set <body> render cell_margin=N`. **The
  ticket's fix, "the body's cell margin (a `sheet` parameter)", did not exist, and the cell is fixed in `render`, not `sheet`:** I added
  `cell_margin` to the character's `render` (default 0, so no hash moved), which grows the measured extents on every side before the
  cell is fitted; N is the smallest margin that holds every Wearable frame (or, when none up to 64 px does, an owner_action).
- **Version bumps:** the Wearable's `render` to 2 (the first render that builds anything; a 0290 build was a stub), its `model` to 2 (it
  was normalised by its own height). `rig` stays 1 (a stub wrote nothing). The character's `render` and `model` did not change what
  they write. **Side effect to know:** `render_frames.py` changed, and its hash is in each body clip's reuse key (`_script_hash`), so
  the next build of a character's `render` renders its clips again even when the Stage is not stale. Its output is the same.
- **Refused:** a body that is a sprite (`wearable.body_not_character`), and a body whose rig came back from Mixamo
  (`wearable.body_rigged`: the rigged file's size and place are the render's, not the Model's, so the Wearable can't be put on it; a
  later ticket can compute the transform). The Wearable's own Model with no armature is `wearable.rig_missing`.
- **Fixtures:** `tests/fixtures/make_render_model.py` takes a fourth argument, `body` (default, as before), `vest` or `both`; new
  `tests/fixtures/characters/render_vest.glb` (the same skeleton, a vest on the chest and a skirt at the hips, inside the body's
  bounds, so the body, the vest and both are normalised alike) and `render_with_vest.glb` (body and vest in one file: the full render
  to compare with). `render_model.glb` is unchanged.
- **Tests:** `tests/cli/test_wearable.py` (fake Blender: clip names and frame counts, the holdout and the body's cell passed through,
  materials after the body's, seconds, `like`, the three waits, rig mismatch both ways, outside_cell and its fix end to end, what a
  body's palette and height do) and `tests/cli/test_blender_render.py` (3 `blender` tests, one shared real render of body, Wearable and
  full). On the real Blender the stack by depth of body and Wearable matches the full render exactly (0 differing pixels in 32 frames,
  37,300 visible), the Wearable's alpha is empty wherever the full render's nearest surface is the body, and what shows of the vest
  from behind (`n`) is 102 px against 430 from the front. Sample sheet (rows are the 8 directions; columns: body, Wearable over the
  holdout shown faint, the stack by depth, the full render, differing pixels in red; 3x), not kept in the repository:
  `C:/Users/KIRILL~1.BRE/AppData/Local/Temp/claude/2a77692328d6afa9/5996f737-0349-4a66-8947-8351433c27d3/scratchpad/wearable_vest_walk1_x3.png`.
- Also changed: `test_character_import.py` (render's parameter list holds `cell_margin`), the spec's §6.3 note.
