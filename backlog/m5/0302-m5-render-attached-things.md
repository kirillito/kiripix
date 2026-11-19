---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0300-m5-clip-attach.md, 0301-m5-held-thing-import.md]
---

# M5: `render` draws a clip's held things at their socket

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- In `blender/render_frames.py`: each thing parented to its socket bone with its `offset` and `turn`, shown only in the clips that
  attach it, its materials in the material pass after the Model's, and included in the measure pass (so the clip's extent holds it).
- `render.json` records each clip's `attach`. `render` Stage `version` bump.
- **Points:** a thing's socket is a point (`render points=hand_r@grip_r` was the trial's fix, 0238 step 5: `hand_r` at the wrist is 2-3 px
  from the grip). Default `points` to include the sockets a clip attaches at, so the game's fallback and the real thing agree.
- The phone vanishes behind the body in many frames (the pose); that's the true depth, and the point's `hidden` flag says so.
- Run on the real Blender in the tests ([0281](0281-m5-real-blender-tests.md)'s seam).

## Acceptance criteria

- [x] Real-Blender test: a fixture character with a socket bone and a thing in one clip: the thing's pixels appear only in that clip, in
      every direction, within a pixel of the socket's point.
- [x] A Model without the socket bone gives `clips.unknown_socket` before rendering.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- **`blender/render_frames.py`:** `things` in the args (every thing of the Asset, `{id, file}`, in numbering order) and a clip's `attach`. `bring_things` brings each thing's
  meshes in hidden (a `.glb` by import, a `.blend` by library load; no parent, no armature modifier, nothing but meshes kept); `begin_clip` shows only the clip's
  things; `pose_clip` puts each at its socket every frame (`place_things`): the bone's head and axes without scale (so the thing keeps Model units), then `offset`
  (x, y, z in that frame) and `turn` (degrees about X, Y, Z), then the thing's own origin and axes are the grip. The measure pass sees them (they are posed before
  `posed_points`), so the clip's `bounds` hold the thing; the camera and depth range are set up on the Model alone. A socket that is not a bone is an error in Blender too.
- **Numbering:** `number_things` numbers the things' materials after the Model's N, thing by thing in the order of `things`, each thing's by name (Blender's `.001` is
  stripped from the reported name), so it is `core.things`' `N + first + place`. Object mask, normal and depth carry the thing. 255 materials in all still fail.
- **`render.json`** (`RENDER_SCHEMA_VERSION` stays 4: additive keys): `materials` is still the Model's own, so `things.model_material_count` is unchanged; `things`
  is `[{"thing", "file", "materials": [{"index", "name"}]}]` for every thing of the Asset when any clip holds one (the key is absent otherwise); each clip entry has `attach`
  (as `clips.json` gives it) when it holds something. A rebuild that keeps every clip takes `things` from the previous `render.json`.
- **Points:** `points` gains `{name, target}` for each socket a clip attaches at, named for the bone (lower case, after the last `:`, other characters `_`; `grip_r@grip_r`;
  `mixamorig:RightHand` is `righthand`), unless a given point already has that name or that target (so the trial's `hand_r@grip_r` is kept, not doubled). They are
  recorded per frame with `hidden` as any point is, and flow to `sheet` and `character.json` as before.
- **Stage:** `render` `version` is **2** (was 1) and takes `THINGS_PATTERN` as an input, so `render` and everything after it is stale on every character. The Stage reads the
  things itself (`_thing_files` in `recipes/render.py`; `imported.jsonl` is a `render` input too, so importing a thing again, which makes an earlier Variant current without a new file, rebuilds; the cost is that any import makes `render` stale, and it then reuses every clip: the journal gives the order and the newest file of the thing's folder, else the last by name). Clip
  and measure keys hold the thing's file name (the hash of its content), and the clip key every thing's, since the numbering reads all of them: adding a thing makes the
  held clips render again, a thing no clip holds changes no number. `_check_held` fails `clips.unknown_thing` / `clips.unknown_socket` before Blender starts. A Wearable's render
  gets no `attach` (`blender_clip` is unchanged), so it holds nothing.
- **`clips.unknown_socket`** already fires at `decide` (rig built) and in the `clips` Stage run; the real-Blender test checks it on the render Model (no `grip_r`) before any render.
- **Tests:** `tests/cli/test_blender_held.py` (real Blender 5.2, marked; the new fixture `tests/fixtures/characters/render_thing.glb`, built by
  `tests/fixtures/make_render_thing.py`): the materials 5 and 6 after the Model's 4; the thing in the holding clip only, in all 8 directions, in the mask; an upright stick's
  column within a pixel of the socket's point in every direction (the grip end is hidden inside the arm, so the stick is turned up out of it); the measured extent holds it.
  `tests/cli/test_render_held.py` (fake Blender): args, `render.json`, current Variant, default points, staleness. The fake Blender returns `things` when it is given some.
- **Note for the fixture:** a thing's grip end sits at the bone's head, which is inside the hand mesh on a real Model, so its first pixels are hidden by the hand. The
  point's `hidden` says the body is in front of the *point*, not of the thing.
