---
status: done
milestone: M4
agent: character-pipeline
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
---

# M4: a `transition` Decision: a clip that blends one clip into another

Spec §6.3 (clips, render). Chosen by the Owner in the trial [0158](0158-m4-transition-clips-trial.md), 2026-11-13: option 1,
a transition clip rendered by Kiripix. Three frames are enough for most transitions.

An idle character that attacks snaps from the idle pose into the attack's first frame. Mixamo exports each animation on its
own, so the blend is made here: Blender interpolates the two poses per bone, and `render` renders the result as a clip of its
own (`idle_to_attack`), exported like any other.

## What to build

- **A `transition` Decision** on `clips` (a `DecisionSpec` beside `CLIP` in `kiripix/recipes/clips.py`):
  - `name`: a clip ID, with the same pattern and the same freeze at the first export as a `clip`. By convention
    `<from>_to_<to>`; Kiripix doesn't enforce it.
  - `from`: `{clip, frame}`, the clip whose pose the transition starts from and one of its game frames (0-based, default the
    last).
  - `to`: `{clip, frame}`, the same for the pose it ends on (default frame 0).
  - `length` (integer, 1 or more, default 3): the transition's frames, **between** the two poses and not including them.
    The `from` frame is the last frame the game shows of the first clip; the `to` frame is the first of the second. The
    transition's frame `i` of `n` is the blend at `(i + 1) / (n + 1)`.
  - `fps` (default: the `from` clip's) and `loop` (always false; not a parameter).
  - Deciding a transition again under its name changes it, as for a clip ([0156](0156-m4-edit-a-clip.md)); `undo` takes it
    back. A name shared with a `clip` fails `clips.duplicate_name`.
- **`clips` resolves it** into `clips.json`: an entry with `transition: {from: {...}, to: {...}, length}`, each end carrying
  the source file's hash, the action, and the action's frame (taken from the named clip's `frames`, so `speed`, `still` and a
  clip's own range are honoured). The entry has no `start` or `end`, and its `frames` are the blend positions `[t1 .. tn]`.
  `clips.json`'s schema version is bumped (refused when older, no migration, as `CLIPS_SCHEMA_VERSION` says).
- **`render` renders it** (`kiripix/blender/render_frames.py`): for each frame, every bone's pose is the blend of the two end
  poses: location and scale linear, rotation by quaternion slerp, in the bones' local space, as the NLA does. The root's
  travel is not blended in; a transition stays in place, like a clip with `root_motion` false. Same camera, cell, passes and
  directions as every clip, and the same cell size for all, so the transition never makes a pose that doesn't fit.
- **The rest follows without change:** `palette`, `finish`, `sheet` and `export` see a clip like any other (frames, fps, loop
  false). `export` names it `<name>_<dir>` and freezes it.
- Cached renders: a transition's frames depend on both end clips' sources and frames, so they're in its render inputs. Changing
  idle's range makes `idle_to_attack` render again, and no other clip.

## Findings

Each has exactly one of `fix` or `owner_action`, and a stable dotted code.

- `clips.transition_missing_clip`: `from` or `to` names no clip. Fix: decide the clip, or undo.
- `clips.transition_frame`: a named frame is not one of the clip's frames. Fix: undo, then decide it again with a frame in range.
- `clips.transition_loop`: `from` or `to` is another transition (a transition between transitions has no meaning). Fix: undo.
- A transition between two poses that are already nearly the same is not a finding; it is only a clip of repeated frames.

## Acceptance criteria

- [x] CLI seam, with the test Kind `demo` or its clip fixtures: deciding `idle_to_attack` (idle's last frame, attack's first,
      length 3) puts a 3-frame entry in `clips.json` whose `transition` names both ends; the same Decision again with length
      5 changes it; `undo` brings 3 back.
- [x] A bad name, a missing clip, an out-of-range frame and a transition between transitions fail with the findings above.
- [ ] `render` of mc02 gives `idle_to_attack` and `attack_to_idle` in every direction, 3 frames each, the same cell as the other
      clips; the first and last frames differ from both end poses; the other clips' frames are byte-equal to before.
- [x] Changing `idle`'s range renders only the clips that read it, among them `idle_to_attack`.
- [x] `export` gives `idle_to_attack_<dir>` animations, and an export after changing the length keeps the IDs.
- [x] `kiripix describe` and the spec's `clips` row say what a transition is.

## Out of scope

- The UI ([0157](0157-m4-ui-edit-a-clip.md) is the clips screen; a transition's controls are a follow-up).
- Choosing which transition the game plays: the game's animation state machine does. Kiripix only names the clips.
- Easing curves other than linear and slerp. A trial would show whether 3 frames need one.

## Notes

- The prototype for this is the trial's script in 0158's folder, once it exists. It isn't a dependency: the Owner has chosen,
  and the build can start from the NLA's per-bone interpolation.
- **Don't run at the same time as** 0213, 0162 or 0148 (`render_frames.py`), or anything else in `recipes/clips.py`
  (0170's build ticket, 0172).

## Result (2026-11-14)

- **`transition` Decision** (`TRANSITION` in `kiripix/recipes/clips.py`, on the `clips` Stage): `name` (a clip's pattern), `from` and
  `to` (`{clip, frame}`, 0-based into the named clip's own game frames; `from` defaults to the last, `to` to 0), `length`
  (default 3, 1 or more), `fps` (default the `from` clip's). Deciding again under a name changes it; `undo` brings it back.
- `CLIPS_SCHEMA_VERSION` is 3. A transition's entry has `transition: {from, to, length}` (each end: `clip`, `frame`, `source`,
  `source_hash`, `action`, `action_frame`, `root_motion`), `frames` = the blend positions `[(i + 1) / (n + 1)]`, `loop` false,
  `root_motion` false, `events` `{"foot": []}`, and no `start`, `end`, `source` or `action`. Its `stationary` is true only when
  both end clips are stationary (so the pivot-drift Check holds a blend of two standing poses to the same rule). Entries are
  sorted by name, clips and transitions together.
- Findings, all with `fix: kiripix undo <asset> clips`: `clips.transition_missing_clip`, `clips.transition_frame`,
  `clips.transition_loop`, `clips.duplicate_name` (a name a `clip` has). A bad name or `length` below 1 is refused at decide.
  A transition with no clip Decision at all is still `stage.needs_input`.
- **Render** (`render_frames.py`): a transition clip is sent as `transition: {from, to}` (action, file, frame, root_motion per end).
  Blender captures each end's per-bone `matrix_basis`, then each frame blends them: location and scale lerp, rotation slerp
  (short way round), set by hand with the action cleared, and the rig is put back at rest after the clip. An end whose clip has
  root motion has its root's travel taken out first (the root bone's translation is moved so the point under it is the ground
  point), and the camera doesn't follow (`root_motion` false). Same camera, directions and passes; the measure pass poses the
  same blend, so the cell fits it. `render.json` is unchanged in format. The key hashes the whole entry, so changing the clip a
  transition reads (when its end frame or source changes) renders it again and no other clip.
- Export: `export/checks.py` counts a transition's `<name>_<dir>` among the frozen IDs; the rest needed no change.
- Spec's `clips` row and `kiripix describe` (the Decision's description, schema and the four Check codes) say what a transition is.
- Tests: `tests/cli/test_character_transitions.py` (20, among them one marked `blender` that renders `idle_to_walk` on the real
  fixture: 3 frames in 8 directions, first and last differ from both end poses and from each other, every other clip's frames
  byte-equal to before). Edited: schema version 3 in `test_character_clips.py` and `test_foot_events.py`, and the `clips` describe test.
- Left for the Owner: the `render` of mc02 (the Owner's art Project isn't available here), where `idle_to_attack` and
  `attack_to_idle` should be 3 frames in every direction at the same cell, and a look at whether 3 frames need an easing curve.
- Not done: the root's bone-axis correction is checked on the fixture's `root` bone only; a rig whose root is the hips with a parent
  chain is handled by the same formula but untested.
