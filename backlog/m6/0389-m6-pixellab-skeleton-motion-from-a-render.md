---
status: done
milestone: M6
agent: ml-engineer
type: ticket
parent: 0386-m6-pixellab-provider.md
depends_on: [0388-m6-gen-paints-a-sprite.md]
---

# M6: `gen --motion skeleton`: a sprite's clip from a character's render

Part of [0386](0386-m6-pixellab-provider.md). In 0354 the worker's walk was best made from mc03's walk: the `render` Stage's
`points` (ticket 0237) give the rig's joints at `top34_8` in every frame, `keypoints.py` turned them into PixelLab's 18 joints,
retargeted them onto the sprite's own skeleton (from `estimate-skeleton` on its first frame), and `animate-with-skeleton-v3`
drew the frames. This ticket makes that Kiripix code. Read `backlog/m6/0354-trial/keypoints.py` and the README's step 3.

## What to build

1. **The mapping, pure** (in `kiripix/providers/`, on plain data, so `providers` still imports nothing else from Kiripix): a
   frame's named points and `eyes` (as `render.json` holds them) to PixelLab's 18 joints (x and y as fractions, `z_index`,
   optional `depth`), with the trial's face joints made from the eyes and the head's bones, and the right side as the
   character's own right. Then the retarget onto the sprite's estimated skeleton (the trial's `retarget`), and the frame pick
   (`--frames N` from a longer clip, evenly).
2. **The points a render needs** are named once (the trial's `POINTS`, Mixamo's bones), and `gen` refuses a render without them:
   `gen.render_points_missing`, with the `fix` `kiripix set <character> render points=<...>`.
3. **`gen sprite.x --clip <name> --motion skeleton --render <character> [--render-clip <clip>] [--frames N] [--directions ...]
   [--from <clip>]`**: core reads the character's `render` output (its `render.json`, current, else `gen.render_stale` naming
   the run), and plans, per direction, `estimate_skeleton` on the sprite's first frame of `--from`, then `animate_skeleton` with
   the retargeted keypoints, as one pending call (0388). The render's directions must cover the sprite's asked ones
   (`gen.render_direction_missing`). Stored as 0388 stores a `--motion rig` clip.
4. **The overlay**: `--preview` (no call, nothing planned) writes the trial's overlay PNG (the render's frames with the joints,
   the right side red) and the keypoints as JSON (`<clip>_<direction>.json`) under `.kiripix/calls/preview/<sprite>/` (not `work/`, which the Stages own), and names
   them in `data`, so the Owner checks the mapping before spending.
5. Spec §6.4's `gen` row gains `--motion skeleton`.

## Acceptance criteria

- [x] The mapping and the retarget on a small committed `render.json` fixture (three frames, two directions): the joints in the
      expected fractions, RIGHT on the character's right, the frame pick. Tested at the CLI seam through the keypoints `gen
      --preview` writes beside its overlay.
- [x] `gen --motion skeleton` with the fake transport plans one pending call of `2 x directions` jobs; the request kept for
      `animate-with-skeleton-v3` holds the retargeted keypoints; `approve` stores the clip.
- [x] A render without the points is `gen.render_points_missing`; a stale render is `gen.render_stale`.
- [x] `uv run mypy`, `uv run lint-imports`. The full suite is [ ] not run (the owner's instruction for this batch: the main session runs it).

Budget: 100–180k tokens.

## Result

Built `kiripix/providers/keypoints.py` (pure), `kiripix/core/gen_skeleton.py` (reads the render, the preview), and changed
`kiripix/core/gen_sprite.py`, `kiripix/commands/gen.py`, the spec (§6.4's `gen` rows) and the fake transport.

- **The mapping** is the trial's, ported unchanged: `POINTS` (Mixamo's bones, named once), `skeleton(frame, size)` (13 body
  joints from the points, the face from `eyes` and `head`/`head_top`), `pick`, `retarget`, `joints_of` (checks an estimate holds the
  18 labels). `depth` is not sent (the trial's `--depth-scale` is not ported: PixelLab takes it from the template).
- **Retarget at send time (decided).** The retarget needs the sprite's estimated skeleton, which exists only after the
  `estimate_skeleton` job. So planning fixes the render's keypoints (fractions of the render's frame) in the animate job's
  `params["keypoints"]` plus `params["retarget"] = {first, size, target}` (the first pose, the render's frame, the sprite's frame),
  all in the pending call JSON the Owner approves; `gen_sprite._feed` moves them onto the estimate when the estimate answers
  and drops `retarget`. It is deterministic, so what is approved is what is sent up to that move. `first_frame_keypoints` is the
  estimate. An estimate without all 18 joints is `gen.rig_unreadable` (the job is not sent; the earlier jobs' charge stands).
- **Refusals**: `gen.render_needed` (no `--render`), `gen.render_not_character`, `gen.render_stale` (not `done`, fix `kiripix run
  <character> render`), `gen.render_points_missing` (fix `kiripix set <character> render points=<POINTS>`, also for a frame that
  lacks one), `gen.render_clip_unknown`, `gen.render_direction_missing`, `gen.frames_range` (3 to 15 for skeleton; also when the
  picked count is under 3), `gen.preview_needs_skeleton`; `--render`/`--render-clip` with another motion is
  `gen.flag_unsupported`. `gen.motion_not_built` is gone.
- **Flags**: `--render`, `--render-clip` (default: the `--clip` name), `--preview`. `--prompt` is optional for skeleton: the
  action defaults to the clip's name (underscores to spaces). The render's first pose is its clip's first frame. A clip is
  `render.json`'s own `frame` when it has one.
- **`--preview`** is `gen_sprite.preview`: no key read, no limits checked, no pending call. It writes
  `<clip>_<direction>.json` (`first_frame_keypoints`, `keypoints`, `meta`) and `<clip>_<direction>_overlay.png` (the render's frames
  with joints, 6x, the right side red; the render's own frames, not retargeted) under `.kiripix/calls/preview/<sprite>/`, and names
  them in `data.preview`.
- **A bug fixed in 0388's rig plan**: the animate job's `needs` was `len(jobs)` after the estimate was appended, so it pointed
  at itself (1, 3), not at the estimate (0, 2); `needs=len(jobs) - 1`. 0388's test already asserts 0 and 2.
- **Tests** (written, **not run**): `tests/cli/test_gen_skeleton.py`. Instead of a committed `render.json`, they use the fake
  Blender (the points go at known places: `[stages.render] points` from the `gen.render_points_missing` fix, `eyes=skin`), so the
  render is really current or stale; the mapping is checked through the preview's JSON (the points' fractions, the eyes with RIGHT
  left of LEFT, the frame pick), the plan, the approved call's request (`keypoints` of the first frame equal the estimate, which the
  fake transport now answers with 18 joints), the stored sheet, and the refusals. `test_gen_sprite.py` expects
  `gen.render_needed` for `--motion skeleton` without `--render`.

Not settled without a real answer (as 0387's note): the field of `estimate-skeleton`'s answer (`keypoints`, a list of `x`, `y`,
`label` as fractions, as the trial read it), and whether `animate-with-skeleton-v3` takes the retargeted fractions as the trial
sent them. The overlay's face joints (nose and ears) are a guess, good to a pixel or two at 52 px.
