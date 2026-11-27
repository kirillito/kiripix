---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0386-m6-pixellab-provider.md
depends_on: [0388-m6-gen-paints-a-sprite.md]
---

# M6: a sprite from one image: a picked image, its other facings, and the camera's view

Follows [0386](0386-m6-pixellab-provider.md). The game's next sprites (a boss raccoon dragging a pizza box, two supernatural
enemies, one-off witness and NPC figures) most often start as **one south-facing image**, styled after a sprite it already
has (`sprite.raccoon`) or a frame of a 3D character's render (mc03), the way the crate and the green bins were made in 0354
(`generate-image-v2` with a style image). Each then needs 4 or 8 facings before `--state` and `--motion` can make its poses.
Kiripix can't do that today:

- `gen prop.x --provider pixellab` paints the image, but as a prop's Variants. Getting the pick into a sprite is a hand
  `import --role sheet` of a repacked ZIP (how `sprite.green_bin` was made).
- `gen sprite.x --from-frames` needs a frame in **every** direction of the sprite (`gen.direction_missing`,
  `gen_sprite._frames_of`), and it stores no sheet, so facings that PixelLab draws are thrown away.
- Every operation sends `view: "high top-down"`, and nothing can change it. The game's characters use `top34_8`'s 30°
  look-down (the game's DEC-054). The 0354 creatures passed with the default, but a PixelLab human next to a 3D-rendered one
  may not.

## What to build

1. **`gen sprite.x --image --prompt "<what>" [--style <asset>[:<clip>] | --style <png>] [--canvas N] [-n N]`**: the plain
   `generate-image-v2` call (0387), with the style image taken from another Asset's frames (the first south frame of the
   clip, `idle` by default; a sprite's `frames` output, or a character's `render` output) or a PNG in the Project. The
   candidates come back as the call's Variants, as a prop's do. Picking one (the same Command a prop's pick uses) stores it
   as a one-direction sheet in PixelLab's layout (`<clip>/rotations/south.png`, clip `idle`, `idle_2`... when held), recorded
   in `imported.jsonl` with the Provider and the call. No hand repack.
2. **`--from-frames` takes the directions the sprite has**, south at least (`gen.direction_missing` only when south is
   missing). When the sprite wants more facings than its frames have, the call makes the others, and **they are stored**: a
   sheet holding the made facings of the `--from` clip, under the next free name (`idle_2`), so the Owner keeps or leaves out
   by the `sheet` Decision (0385), as with a retried state. The sent south frame stays as drawn.
   - Which endpoint draws them is this ticket's first job. Make one trial call each way on the raccoon's south frame
     (cents; Owner's `approve`), record both in this ticket, and keep the one whose south frame comes back unchanged and whose
     other facings keep its size and palette:
     - `create-character-v3` with `reference_image` alone (no `direction_images`), which already gives the character ID that
       `--state` needs;
     - `generate-8-rotations-v3` (about $0.03 at 32 px, 2026-11-25), then `create-character-v3` from all the frames.
   - A 4-direction sprite (the game's Waiting Ones) gets 4 facings, not 8.
3. **The view is a setting of the character.** `[sprite.pixellab]` gains `view` (`"high top-down"` by default; PixelLab's
   other values as its schema lists them). `gen --prompt` and `--from-frames` take `--view` and store it. It reaches PixelLab only
   where the endpoint takes one: the character call, the rotations, and rig and skeleton motion. The state call and
   `animate-with-text-v3` take no view, and `generate-image-v2` has none, so `--image`, `--state` and `--clip` refuse `--view`
   (`gen.flag_unsupported`). `kiripix show` names it.
4. Spec §6.4's `gen` rows and `describe gen` gain `--image`, `--style` and `--view`; the price table gains whatever endpoint
   item 2 keeps.

Before building, read the endpoints' request schemas from PixelLab's API docs (`api.pixellab.ai/v2/docs` renders by script;
its OpenAPI JSON is the source). Terms as 0386: code calls `api.pixellab.ai` only.

## Acceptance criteria

- [x] With the fake transport: `gen sprite.x --image --style sprite.y` plans one call whose request holds `sprite.y`'s south
      frame as `style_image`; a pick stores a one-direction sheet the `frames` Stage reads with no change.
- [x] `--from-frames` on a south-only 8-direction sprite plans one pending call; `approve` stores the 7 made facings (plus
      the south frame as sent) as clip `idle_2`; the sprite's `[sprite.pixellab]` holds the character ID. On a 4-direction
      sprite, 4.
- [x] `--view "low top-down"` is in the request of the character call and of a later rig or skeleton motion call (not of a
      state call, which has no view); `--image --view` is refused.
- [x] The two trial calls of item 2 and the choice are recorded in **Result**, with their charges.
- [x] New and changed Commands have samples in `tests/cli/test_contract.py`; `uv run mypy`, `uv run lint-imports`.

Budget: 150–250k tokens.

## Result

Status: done. Built and tested over the fake transport; the item 2 trial ran (2026-11-27, a throw-away copy of the game's art
Project, `sprite.raccoon` made south-only from its `idle/south.png`, 32x32) and the Owner chose the rotations path.

Schema source: PixelLab's OpenAPI JSON (`https://api.pixellab.ai/v2/openapi.json`, a free GET, read 2026-11-26). It showed:
`create-character-v3`'s `view` is `low top-down | high top-down | side` (API default `low top-down`; Kiripix keeps
`high top-down`), `direction_images` never holds `south` (the reference), reference alone costs `ceil(w*h*8/65536)`
generations and a fully covered set 0.25; `generate-image-v2` has **no `view`**, so `--view` with `--image` is refused
(`gen.flag_unsupported`) instead of stored; `generate-8-rotations-v3` returns 8 frames clockwise from south, the first as sent.

Built:
- `gen --image [--style] [--canvas] [-n]`: a plain pending call (`gen_sprite._plan_image`); candidates stored in `src/` as Variants
  (`sources.import_generated_variant`, recorded with Provider and call); `show` lists them; `pick` on a sprite (`gen_sprite.pick`)
  stores a one-direction sheet `idle/rotations/south.png` (`idle_2`... when held). `--style <asset>[:<clip>]` takes a sprite's
  `frames` or a character's `render` (`gen_skeleton.first_frame`), or a PNG.
- `--from-frames` takes the directions the sprite has (`_frames_of(south_only=True)`), makes the missing facings with
  `generate-8-rotations-v3` on the south frame, then `create-character-v3` from all the frames (0.25 generations), and stores
  the made facings plus the sent frames as clip `<from>_2`. A sprite that has every facing sends only the second call and stores
  no sheet. A 4-direction sprite gets 4 facings.
- `[sprite.pixellab] view` (default `high top-down`; `asset.toml` `schema_version` 2, ticket 0391's migration); `--view` on
  `--prompt` and `--from-frames`; rig and skeleton motion send the stored view, the state call has none to send. `show` names the character and view.
- Fix found on the way: the Provider sent `south` in `direction_images`, which the OpenAPI forbids; removed. No Stage `version`
  bump; no `schema_version` bump for the pending call (2) or `imported.jsonl` (2).
- Prices, dated 2026-11-27 (`PRICES_DATE`): `ROTATIONS_USD` 0.0203 (generate-8-rotations-v3 at 32 px), `CHARACTER_FROM_FRAMES_USD`
  0.0043 (create-character-v3 from all frames). The `--facings` flag, `FACINGS`/`FACINGS_BY` and the reference-alone path and
  price are deleted.

## Trial (2026-11-27)

- Call 01M8D8F2W1G1DQ6HEPCYEZVVDN, `create-character-v3` with `reference_image` alone: $0.023991. South came back unchanged,
  the made facings are 32x32 and use 25 colours, 23 of them the south frame's 23. By eye, the back and three-quarter-back views
  were grey blobs.
- Call 01M8D9J88T035YZ3MKR3JRTJ7T, `generate-8-rotations-v3` ($0.020301) plus `create-character-v3` from all frames ($0.004325),
  $0.024626 in total: same size and colour figures, with coherent back views, a consistently striped tail and visible legs.
  **The Owner chose this one (2026-11-27).**
- The first try of the rotations call failed with HTTP 422 ("view is only used with direction_images: a single sprite is
  rotated as drawn. Drop view or add direction_images."); no charge was recorded. `_rotations` in the Provider now sends `view`
  only with `direction_images`; the fake transport refuses the same way and the test asserts it.

Open, not fixed:
- `--from-frames` takes no description, so PixelLab's description is the Asset's name (`raccoon_s` would send "raccoon s").
- The `frames` Stage raises `frames.direction_missing` on a south-only 8-direction sprite yet still builds.

Tests: `tests/cli/test_gen_sprite.py` (0390 section), `test_contract.py::test_a_sprites_image_pick_and_show_validate`.
