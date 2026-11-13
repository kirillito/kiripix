---
status: review
milestone: M4
agent: none
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0159-m4-part-vanishes-check.md]
---

# M4: stamped eyes, blinks and winks, and still and faster clips

Spec §6.3. Asked for by the Owner on 2026-11-13, after mc03 went through Mixamo and Kiripix: bigger eyes in the Model
([0197](0197-m4-mc02-bigger-eyes.md)) made the eyes vanish less, but they still changed shape in every frame of an idle, "3 to
5 black pixels flowing around the face", where a Chrono Trigger sprite's eyes are a fixed pattern with a white.

## The gap

`render` samples each pixel's centre, so an eye two pixels wide changes with every sub-pixel move of the head. A bigger eye
in the Model doesn't end that. Three more things the Owner asked for, which the clips couldn't say:

- an idle that stands still;
- blinking;
- clips that play faster, with fewer frames, than the Mixamo action.

## What was built

- **`render eyes=<materials>`**: Blender reports where each eye is in every frame, from the posed mesh: its centre, extent,
  depth and normal. An eye is the faces of the named materials on one side of the Model's middle. `render.json` gets `eyes`
  and each frame an `eyes` list; nothing is written when the parameter is empty.
- **`finish eyes=stamp`** (or `pupils`, without whites): the rendered eye pixels are filled with the skin round them and each
  eye is painted as a small pattern (Ops `plan_eyes`, `fill_from_neighbours`, `paint_eyes` in `kiripix/ops/eyes.py`). The
  pattern is chosen once for a clip and a direction; per frame only its place changes, on whole pixels, and only when the
  head has moved three quarters of a pixel. An eye is left out where it faces away or sits behind something (the depth pass).
  `eye_colour` and `eye_white` are Project palette indexes; -1 picks the rendered eyes' commonest colour and the palette's
  lightest.
- **`clip` Decision**: `blink` (the frames drawn with closed eyes), `wink_left` and `wink_right` (one eye closed), `still` (the pose at `start` held for that many frames)
  and `speed` (the action plays that many times faster). `clips.json` and `render.json` carry them only when set, so the
  entries of existing clips are unchanged.
- `sheet.part_vanishes` doesn't watch the eye materials when the eyes are stamped.

## Acceptance criteria

- [x] With `eyes=stamp`, a stationary clip's eyes are the same pixels in every frame but a blink
      (`tests/cli/test_character_eyes.py`).
- [x] A sway of less than a pixel doesn't move the eyes; a bigger one moves both together (`tests/golden/test_eye_ops.py`).
- [x] An eye facing away is not painted; `eyes=stamp` without followed eyes fails with a fix.
- [x] `still`, `speed` and `blink` reach `clips.json`; a blink past the last frame fails with a fix.
- [ ] The Owner sees it in the game on mc03 (male and female) and says the eyes read as eyes.

## Open

- The new parameters make `render` and `finish` stale on every character, and the changed render script renders every clip
  again. A Kiripix code change alone doesn't make a Stage stale: after an update to the render script, `render --force`, then
  `palette`, `finish`, `sheet` and `export` with `--force`.
- The pattern has no look direction and no mouth, so no smile: a mouth would be a second stamp, from a `mouth` material in the
  Model. The white is one colour for every character.
- The UI has no controls for `blink`, `still` or `speed` (the `clip` Decision takes them from the CLI).
- The real Blender path (`eye_groups`, `posed_eyes`, `seen_eyes` in `render_frames.py`) was run on mc03 in a scratch Project,
  not in a marked Blender test.
