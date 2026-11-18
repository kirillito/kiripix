---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
---

# M5: an Op that picks one set of colours for several images, and keeps their gradients

Spec §7 (colour Ops). Part of [0240](0240-m5-portrait-kind.md). Used by the portrait's `palette` Stage
([0243](0243-m5-portrait-recipe.md)).

## Why

The Owner, 2026-11-16: portraits are generated, "they shouldn't depend too much on character sprites", and "there will be
gradients at portraits that will definitely not match strict sprite palette requirements". So a portrait set gets colours of
its own, chosen once over every emotion so a shade can't flip between them. It doesn't map to the Project's palette, and
it doesn't use the Ramp table.

## What to build

In `kiripix/ops/`, pure:

- `set_colours(images, alphas, n, keep=()) -> palette`: k-means in OKLab over the opaque pixels of every image together,
  weighted so each image counts equally. `n` colours in all, the `keep` colours among them (for example the outline colour,
  or Project colours the Owner wants shared). Deterministic: a fixed seed and the images' order doesn't matter.
- `map_set(images, palette, dither) -> images`: each image mapped to the set's colours with the existing nearest-colour and
  ordered-dither Ops, so a smooth gradient can stay smooth with enough colours, or dithered with fewer.
- A report per image: the mean and the 95th-percentile OKLab error, and the colours each image uses.

## Acceptance criteria

- [x] Golden seam: two images of one gradient, one shifted by a pixel, map to the same colours wherever their pixels match.
      At `n` 8 against 32 the error report drops.
- [x] Unit cases: the `keep` colours are in the result; reordering the images changes nothing; every output pixel is a set
      colour.
- [x] Exported from `kiripix.ops`. `uv run lint-imports` and `uv run mypy` pass.

## Result

`kiripix/ops/colourset.py`, exported from `kiripix.ops`:

- `set_colours(images, alphas, n, keep=())` returns up to `n` sRGB colours, `keep` first and unchanged. `alphas` is a
  list of opaque masks, or None to read each image's alpha. Each image weighs the same; colours and weights are merged in
  a canonical order, so the image order changes nothing. Seeds go where the pixels are worst served, then 24 Lloyd rounds.
- `map_set(images, palette, dither)` maps each RGBA image with `quantize` (nearest in OKLab, Bayer dither).
- `set_report(before, after)` gives a `SetReport` per image: mean and 95th-percentile OKLab error, colours used.

Tests: `tests/golden/test_colour_set.py`; golden `tests/golden/expected/colour_set_shifted.png`. Spec §7 updated.

Review fix: a cluster mean that rounds onto a `keep` colour or another centre no longer shrinks the set. The gap is
filled with the worst-served pixel colour, so `set_colours` returns exactly `n` colours when the opaque pixels have at
least `n` distinct ones, and fewer only when they have fewer. Tests added for both. Stray blank lines removed.
