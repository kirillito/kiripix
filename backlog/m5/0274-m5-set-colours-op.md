---
status: todo
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

- [ ] Golden seam: two images of one gradient, one shifted by a pixel, map to the same colours wherever their pixels match.
      At `n` 8 against 32 the error report drops.
- [ ] Unit cases: the `keep` colours are in the result; reordering the images changes nothing; every output pixel is a set
      colour.
- [ ] Exported from `kiripix.ops`. `uv run lint-imports` and `uv run mypy` pass.
