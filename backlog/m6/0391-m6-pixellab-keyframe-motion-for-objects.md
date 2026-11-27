---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0386-m6-pixellab-provider.md
depends_on: [0388-m6-gen-paints-a-sprite.md]
---

# M6: `gen --motion keyframes`: an object's clip between two of its frames

Follows [0386](0386-m6-pixellab-provider.md). 0386 left out text-driven animation (`animate-with-text-v3`) because it melts
faces. Objects have no faces, and the one object animated so far needed exactly that call: the game's green bin topple
(`animate-with-text-v3`, first frame `standing`, last frame `toppled`, 8 frames, $0.019, run 112 in `0354-trial/runs/`),
which the Owner kept. More such clips are coming: a bin toppled in a boss fight, a crate opening, perhaps an enemy fading on
defeat. Each was made outside Kiripix and imported by hand.

**Image-referenced, never text-only (Owner, 2026-11-25).** Motion from a start frame and a text alone gave bad results in
0354 and stays out. This route always sends **two of the sprite's own frames, a start and an end**; the text only names the
action between them. That is how the kept bin topple was made.

## What to build

1. **`gen sprite.x --clip <name> --motion keyframes --from <clip> --to <clip> --prompt "<the action>" [--frames N]
   [--directions s,...]`**: per direction, one job with the first frame of `--from` as the start and the first frame of
   `--to` as the end, as one pending call (0388). `--to` is required: without it, `gen.keyframes_need_end` (no call made
   from one frame and text). Stored as a `--motion rig` clip is
   (`animations/<name>/<direction>/frame_NNN.png`, the next free name on a retry).
2. **Only for a sprite marked faceless:** `[sprite.pixellab]` gains `faces` (true by default). Without `faces = false`,
   `--motion keyframes` is `gen.keyframes_faces`, with the `owner_action` `kiripix set <sprite> pixellab faces=false` (the Owner's own choice, not a `fix` an agent runs). So the Owner's
   rule stands for anything with a face, and setting it is a conscious choice.
3. **The endpoint:** `animate-with-text-v3` with both frames (up to 16 frames, max 256 px; about $0.022 at 32 px and 4
   frames, 2026-11-25) by default. `interpolation-v2` (in-betweens of two images, Pro, $0.08 to $0.15) only if
   the trial below shows it holds the object's shape better; record which in **Result**.
   - Trial: the bin topple again (`sprite.green_bin`, `standing` to `toppled`, 8 frames) through `gen`, both ways if the
     second is wanted. 0236 saw frame 3 morph instead of rotating; its next idea was a 45° key pose and two shorter clips.
     Joining two clips into one is the `sheet` Decision's business (0385), not this ticket's; say in **Result** whether the
     Decision can already do it.
4. A one-direction sprite (the bin) works; `--directions` defaults to the sprite's own.
5. Spec §6.4's `gen` row and `describe gen` gain `--motion keyframes` and `--to`; 0386's "Not called" line is amended to
   "text-driven motion from one frame".

## Acceptance criteria

- [x] With the fake transport: a faceless one-direction sprite plans one job whose request holds the start and end frames;
      `approve` stores the clip, which the `frames` Stage reads unchanged.
- [x] Without `faces = false`, `gen.keyframes_faces` with its `owner_action` (exit 3); without `--to`, `gen.keyframes_need_end`; nothing
      is planned in either case.
- [x] The trial call(s), their charge and the endpoint kept are in **Result**.
- [x] Contract samples; `uv run mypy`, `uv run lint-imports`.

Budget: 80–140k tokens.

## Result

Done. The code, the tests and the docs are done, and the trial ran on 2026-11-27 (below).

**Built.** `gen <sprite> --clip <name> --motion keyframes --from <clip> --to <clip> --prompt "<the action>" [--frames N]
[--directions s,e]`: per direction one `animate_keyframes` job (`animate-with-text-v3`), the first frame of `--from` as
`first_frame` and the first frame of `--to` as `last_frame`, one pending call under one approval (0388). Stored as a rig's
clip is (`animations/<name>/<direction>/frame_NNN.png`, `<name>_2`... on a retry), so the `frames` Stage reads it unchanged.
- **Schema read from PixelLab's OpenAPI** (`https://api.pixellab.ai/v2/openapi.json`, free GET, 2026-11-26). `animate-with-text-v3`:
  `first_frame*`, `last_frame` (optional, base64 image, at most 256 px), `action*` (at most 1000 characters), `frame_count` (4 to
  16, **even**, default 8), `seed`, `no_background`, `drift_threshold`, `enhance_prompt`; width x height x frames at most 524288.
  The two keyframes are not said to be in the answer: whatever frames come back are stored as they are. `interpolation-v2`:
  `start_image` and `end_image` (each `{image, size}`), `action` (at most 500), `image_size` (16 to 128), `seed`,
  `no_background`, `target_palette`; **no frame count** (14 frames up to 64 px, 2 from 65 px), in-betweens only, Pro, 10
  generations up to 128 px (about $0.08 to $0.15). Its frame count and 128 px cap fit an 8-frame clip of a 32 px object badly,
  so **`animate-with-text-v3` with both frames is the endpoint kept for now, and `interpolation-v2` is not wired**; the trial
  can say if it is wanted.
- A frame over 256 px is `gen.canvas_range` (after the review; it was a `gen.frames_range` whose fix failed again).
- `--frames` is an even 4 to 16 (default 8) and width x height x frames at most 524288 (`gen.frames_range`, its `fix` a valid
  count); both frames of a direction must be one size (`gen.frames_differ`).
- **Refusals, nothing planned, no key needed:** `gen.keyframes_need_end` (no `--to`, its `fix` adds `--to <clip>`);
  `gen.keyframes_faces` (the sprite isn't marked faceless; **an `owner_action`, exit 3**, naming `kiripix set <sprite> pixellab faces=false`, after the review: marking a sprite faceless is the Owner's choice);
  `--to` with another motion is `gen.flag_unsupported`.
- **`[sprite.pixellab] faces`** (true when absent, not written when true; `asset.toml` `schema_version` is now 2, a pure migration 1 to 2 that adds nothing, after the review). So the table can be set
  on a sprite no call has made a character of (the hand-imported bin), `character_id`, `canvas` and `made_from` became optional,
  all three or none; `view` is not written for such a table while it is the default. A state or a rig motion still needs a
  character (`gen.character_needed`); a later character call keeps `faces`.
- **`kiripix set <sprite> pixellab faces=false`** (`faces` only; the view is set when the character is made): `set` took only Stage parameters, so `editing.set_params_many`
  gained this one table (a sprite's; another kind is `stage.unknown`; a bad key `set.unknown_parameter`, a bad value
  `set.invalid_value`, each with the `fix` `kiripix show <sprite>`, never a fix that sets `faces`). `show` prints and returns `faces` and tells a faceless sprite.
- Estimate: `KEYFRAMES_USD` in the Provider, $0.022 up to 4 frames, $0.03 to 8, $0.045 to 16 (0.022 is the ticket's figure at
  32 px and 4 frames; 0.019 measured at 8 in run 112; the rest cap-safe guesses). PixelLab's charge counts once known.
- Docs: spec §6.4 (the `gen` row), `describe gen` / `gen --help` (and the regenerated command index), 0386's "Not called" line.
- **No Stage `version` bump:** no Stage changed what it writes; `frames` reads the stored clip as it reads a rig's.
- Tests (`tests/cli/test_gen_sprite.py`, `test_contract.py`; the fake transport in `tests/fixtures/kiripix_test_recipes.py`
  answers `animate-with-text-v3`, refusing an odd or out-of-range `frame_count` as the OpenAPI does).

**The `sheet` Decision (0385) and two clips.** It cannot join two clips into one. It places a PNG sheet as one clip
(`{file, clip, ...}`) or renames and leaves out the clips of a ZIP (`{file, clips, leave_out}`); every clip of a sheet stays a
clip of its own. Two generated halves (`topple` and `topple_2`) would stay two clips in `frames.json`; joining them into one
clip is not something it does yet, so a "two shorter clips" answer to 0236's morphing frame needs its own ticket.

**Trial (2026-11-27, the Owner's approval).** Run in a throw-away copy of the game's art Project, so the game's own
`sprite.green_bin` is unchanged. Commands: `kiripix set sprite.green_bin pixellab faces=false`, then `kiripix gen
sprite.green_bin --clip topple --motion keyframes --from standing --to toppled --prompt "the green bin topples over onto its side"
--frames 8`, approved as call `01M8D8FTZWY1EG98HEGH9FAYMP`: one `animate-with-text-v3` job, **$0.018663** (estimate $0.03),
9 frames of 32x32 back (8 asked; the answer's count is stored as it comes), stored as clip `topple_2`.
- **The Owner judged it worse than the kept clip** (run 112): the bin is squashed toward the front, then falls open to the side
  all at once. The cause is the keys, not the call: `toppled` lies on its side, while a bin falling from a south-facing
  `standing` falls toward the viewer. A keyframe clip needs an end frame that the motion can reach from the start; for this
  topple, a `toppled` drawn fallen forward (made with `gen --image --style sprite.green_bin`, 0390, then kept as a clip).
- **Endpoint kept: `animate-with-text-v3`** with both frames. `interpolation-v2` was not tried: its 14 or 2 frames and Pro price
  don't fit a 32 px object's 8-frame clip, and the trial's fault was the end key, which an in-betweener would follow too.
- Estimate: `KEYFRAMES_USD` stays on the cap-safe side ($0.03 at 8 frames; measured $0.0187 here, $0.019 in run 112).
- **The game's bin topple** stays the one made in 0354 (run 112). A forward topple, with a new end frame, is the game's backlog.
