---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0242-m5-portrait-asset-and-emotions.md, 0274-m5-set-colours-op.md]
---

# M5: the portrait's Stages: cutout, register, fit, palette, finish

> **On hold (the Owner, 2026-11-18).** The design below assumes the body never changes between emotions (`register`,
> `lock_outside_face`, `portrait.shimmer`). The Owner wants portraits that express emotion with the whole body, so those
> parts are in question; see [0241](0241-m5-portrait-trial.md) "The Owner's view" and [0240](0240-m5-portrait-kind.md). Don't
> start until 0240 is redesigned. Kept from the trial: the key tolerance, the white-rim removal (and a Check for
> leftover rim specks, which differed between emotions), one scale and `n` colours for the set, the outline placement.
>
> **Redesigned 2026-11-19** (the game's 0091; [0241](0241-m5-portrait-trial.md), "Answers after the redesign"). The
> changes to what's built here are [0321](0321-m5-portrait-whole-body-emotions.md) and [0322](0322-m5-portrait-light-rim-check.md).

Part of [0240](0240-m5-portrait-kind.md). Its table is the design, with the trial [0241](0241-m5-portrait-trial.md)'s
changes the Owner accepted (2026-11-18, 0240's Answers). The trial's prototype, `0241-trial/portrait_set.py`, is the
reference for each step.

## What to build

- **`cutout`:** the Prop's, run on the neutral image and on every picked emotion. A BiRefNet call is pinned per image.
  The chroma key needs what the trial found an image model's JPEG gives: a key `tolerance` (OKLab, the trial's 0.06,
  from the border's median, which differs per image), removal of a white sticker rim around the figure, and green-spill
  removal on the edge. Island removal needs a faster Op than `remove_small_pieces` (about 10 s an image at 896 x 1200).
- **`register`:** each emotion to the neutral, with the Looks' registration Op, outside the `face` region when there is one
  (a `face` Decision: a polygon or a brush, as the Looks' regions). Writes each emotion's transform and residual.
  `portrait.misaligned` is an error over half a target pixel, or when registration hits its limits, with an `owner_action` to
  re-make the edit.
- **`fit`:** one Grid transform from the neutral onto the canvas at the anchor, applied to every registered emotion. The alpha
  goes to the grid by majority vote.
- **`palette`:** the set's own colours, with [0274](0274-m5-set-colours-op.md)'s Ops: `mode=set` (default; `n` default 32
  and up to 256, since the Owner wants more colours eventually; `dither` default 0;
  `keep` with the outline colour always kept), `project` (the Prop's strict mapping) or `off` (colours kept, only the alpha
  binary). Orphans removed per image. `palette.json` records the set's colours. The Check is "every pixel on the set's
  colours", not on the Project's (spec §2, principle 6's portrait exception).
- **`finish`:** the outline in `outline_colour`, with a `placement` parameter, default `edge` (the image model already
  draws a dark outline, so `outside` doubles it to about 2 px). `lock_outside_face`: outside the `face` region every
  emotion takes the neutral's pixels, on by default when a `face` region is drawn (the trial: 1,000-1,300 px of shimmer
  an emotion without it, 0 with it). The region must hold everything meant to change, a raised hand included.
  `portrait.shimmer` (info) reports, per emotion, the pixels outside `face` (or all of them, without one) that differ from
  the neutral's, with boxes.
- **Status:** a new emotion adds work only for that emotion where it can. A refit or a new palette rebuilds all of them. A
  `face` change makes `register` stale and does not put it in needs-review (the Owner's decision, 2026-11-18: the UI reruns
  `register` after each stroke and the portrait is being redesigned around whole-body emotions, see 0241; pinned by a CLI test,
  ticket 0298).
- Long loops (per image, per emotion) check the cancel token.

## Acceptance criteria

- [x] CLI seam, on a fixture set (a neutral and two emotions shifted and scaled by about 1 %, made in the test): after
      `finish`, every image is the canvas's size, the body outside the face is pixel-identical to the neutral's, and the
      residual is under half a pixel.
- [x] An emotion shifted past the limits gives `portrait.misaligned`.
- [x] A fixture whose emotions differ only by noise outside the face: with the lock, the body outside the face is the
      neutral's exactly; without it, `portrait.shimmer` counts the noise.
- [x] `portrait.shimmer` counts a known change outside the face. Every pixel is on the set's colours, and the alpha is
      binary.
- [x] Golden seam for any new Op. `uv run lint-imports` and `uv run mypy` pass.

## Result

Built by the imaging-engineer. The Stages are in `kiripix/recipes/portrait_set.py` (declared in `portrait.py`); `export` is
0244. Every Stage works on the whole set and writes the neutral as `<image>` and each emotion as `emotions/<id>.png` in its
folder (`work/<stage>/`), plus a record that lists the emotions in declaration order.

**New Ops** (`kiripix.ops`, golden tests in `tests/golden/test_portrait_ops.py`): `border_colour`, `chroma_key_tolerant`,
`remove_key_spill`, `remove_light_rim`, `remove_small_islands` (same result as `remove_small_pieces`, which stays; 0.6 s for the
whole cutout of a 896 x 1200 image against about 10 s, by joining runs of rows), `mask_touching_target` (a Mask to the target
grid wide: a cell is set when any pixel is). On the trial's `neutral.jpeg` they clear what the prototype did (rim and spill about
17,000 px, 70 px of islands, 0 fringe).

**Version bumps:** none. All five Stages were declared stubs with no run function and were never built, so there is no output
to go stale; they start at `version` 1. `brief` and `source` are unchanged. Note for later: `_CODE_VERSION` in `portrait_set.py`
keys the per-image reuse in `cutout` and `register`; bump it together with those Stages' `version`.

### What 0244 (export) and 0245 (UI) can read

- **`brief/brief.json`:** `width`, `height`, `anchor` `[x, y]`, `fallback` (0242). **`source/emotions.json`:** the emotion IDs in order.
- **`fit/grid.json`** (the Grid, no `schema_version`, as a Prop's): `mode` `"downscale"`, `source` `[w, h]`, `anchor`, `emotions`
  (IDs in order), `face` (bool), and the Grid's `scale_x`, `scale_y`, `offset_x`, `offset_y`, `width`, `height`, `pad_*`. A
  click or a box in canvas pixels maps to the neutral's source pixels through it (`kiripix.ops.Grid`). `fit/face.png` is the
  face region in canvas pixels (1-bit, every cell the region touches), present only when a face is drawn.
- **`finish/finish.png`** (neutral) and **`finish/emotions/<id>.png`**: the final images, RGBA, canvas size, binary alpha, every
  opaque pixel one of the set's colours. **`finish/finish.json`** (`schema_version` 1): `emotions`, `outline` (`drawn`,
  `colour`, `placement`), `face` (a region is drawn), `locked` (the lock was applied), `shimmer` per emotion
  (`exact`, `visible`, `boxes`: `x`, `y`, `width`, `height`, `pixels`, largest first, at most 8).
- **`palette/palette.json`** (`schema_version` 1): `mode`, `n`, `colours` (`[[r, g, b], ...]`, the set's colours, outline included),
  `outline`, `images` per ID (`mean_error`, `p95_error`, `colours` used). The export Check "on the set's colours" reads `colours`.
- **`register/register.json`** (`schema_version` 1): `emotions`, `face`, `target_scale`, `images` per emotion: `scale`, `shift`
  (source px), `residual` (source px), `residual_target`, `tiles`, `applied`, `problems`. `register/face.png` is the region in
  the neutral cutout's pixels. **`cutout/cutout.json`**: per image `chroma` (the key used), `keyed`, `spill`, `rim`, `islands`.
- **Findings:** `portrait.misaligned` (error, `owner_action`; `data`: `emotion`, `problems`, `residual`), `portrait.residual` (info,
  per emotion; `data`: `emotion`, `scale`, `shift`, `residual`, `tiles`, `applied`), `portrait.shimmer` (info, per emotion with
  any difference; `data`: `emotion`, `exact`, `visible`, `boxes`, `face`, `locked`; positioned at the largest box),
  `palette.set_error` (info; `data`: `mode`, `colours`, `images`), plus the Prop's `cutout.chroma_*`, `fit.size_mismatch`,
  `image.partial_alpha` and `palette.off_palette`. `portrait.shimmer` is measured on the finished images before the lock, so it
  reports what the lock removed; `visible` counts a difference over 0.03 OKLab, or one opaque and one clear pixel.
- **Parameters:** `cutout`: `method` (chroma, matting), `chroma` (`auto` = each image's border median, or `#RRGGBB`), `tolerance` 0.06,
  `spill_reach` 3, `rim_reach` 10, `islands` 1500. `fit`: `offset_x`, `offset_y` (-1 = from the anchor). `palette`: `mode`
  (set, project, off), `n` 32 (1 to 256), `dither` (none), `keep` (hex colours), `outline_colour` (a Project palette index,
  default 0), `orphan_size` 1. `finish`: `outline` true, `placement` edge, `lock_outside_face` true. The `face` Decision is on
  `register`: `points` plus an optional `radius` (a brush) and `erase`, in the neutral cutout's pixels; it is `on_image`, so a new
  neutral Source puts `register` in needs-review, while a `face` edit only makes it stale (0298).

### Decisions I made that the ticket left open

- **`outline_colour` is a `palette` parameter**, not `finish`'s: the palette must keep the outline's colour among the set's, and
  `finish` reads it from `palette.json`. `finish` has `outline` and `placement`.
- **The `face` region is drawn in the neutral cutout's source pixels** (register runs before fit, so no Grid exists yet); `fit`
  maps it to canvas pixels wide (every touched cell), so the lock never cuts a face.
- **The outline never runs along the canvas's edge**: the cut of a waist-up crop gets no line, for `edge` and `outside` alike.
- **`fit` has no `mode`**: always `Grid.cover` (one scale from the neutral), the crop placing the figure's centre column and its lowest
  row on the anchor; `offset_x` and `offset_y` of 0 or more override it.
- **A face can be drawn only once `cutout` is built** (the Decision is made on that image).

### Left open

- "A new emotion adds work only for that emotion": done for `cutout` and `register` (per-image reuse, said in the run's message).
  `fit`, `palette` and `finish` rebuild every image, because the set's colours and the shared crop depend on all of them.
- Registration ran on synthetic fixtures (shifts and scale of about 1 %), not on a re-run of the trial's JPEG set; the trial's
  residuals (0.03 to 0.09 source px) are not re-measured.
- Tests: `tests/cli/test_portrait_stages.py` is about 90 s with `-n 6` (each test builds a set through the CLI).

### Review fixes (2026-11-18, main session)

- `grid.json` carries `schema_version` (the set's record version, 1) and `read_record` checks it like the others; it records
  `figure` (the fitted neutral's `centre_x` and `foot_y` on the canvas), which `export.portrait_canvas` reads.
- An emotion that registration can't measure (no textured tile outside the face, flat colours) gives a `portrait.misaligned`
  warning that it is used unregistered; before, it passed silently.
- `portrait.emotion_unpicked` carries `data.emotion` (a needs-input finding can now carry `data`: `NeedsInput.data`).
- One `_HEX` check for `chroma` and `keep`; one `_placed` for a shared Check's findings.
- Kept as built: `portrait.shimmer` counts before the lock, so with the lock on it reports what the lock replaced (its message
  and `data.locked` say so). Left for [0298](0298-m5-portrait-reads-and-face-review.md): the `face` needs-review rule.
