---
status: done
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: the Layer Ops

Spec §7 (masks, compose), §6.1 and ADR 0004. Pure, numpy only, golden-tested, each exported from `kiripix.ops`.

## What to build

- `grow_where_partial(alpha, partial, pixels)`: widens a binary Mask by N target pixels, only into or through pixels
  `partial` marks; 0 changes nothing. The Op takes `partial` as given; what counts as partial is the Stage's.
- `partial_cells(mask_on_source, grid)`: target pixels whose Source cell is neither all set nor all clear, for a binary
  Runner Mask.
- `mask_from_difference(full, plate, threshold)`: where two images of one size differ by more than an OKLab distance.
- `recompose(plate, layers)`: Layers over the Plate, in order, unblended.
- `cut_by_alpha(image, alpha)`: an image with alpha applied, transparent elsewhere.
- `connected_regions(mask)`: stable-ordered 4-connected regions, for holes and differences.

## Settled (Owner, 2026-11-04)

- `grow_where_partial`: 4-neighbour dilation, N steps; each step adds only neighbours `partial` marks. Boolean in and out.
- `partial_cells`: a cell is partial when some but not all of its Source pixels are set; Source pixels outside the Grid
  are ignored.
- `mask_from_difference`: OKLab distance on RGB, strictly greater than `threshold`. Transparent in one image only counts
  as different; transparent in both doesn't, whatever the colour.
- `recompose`: `overlay` folded over the Layers in order; a painted pixel replaces the one below.
- `cut_by_alpha`: (0, 0, 0, 0) outside the Mask, the pixel unchanged inside.
- `connected_regions`: a list of (n, 2) int64 arrays of (y, x) pixels in raster order, the regions ordered by their first
  pixel in raster order.

## Acceptance criteria

- [x] A golden test for each Op, compared pixel-exactly, including `grow = 0`, an empty Mask and overlapping Layers.
- [x] `recompose(cut plate, cuts of the image by alpha)` returns the original image exactly, in a golden test.
- [x] `uv run lint-imports` passes: `ops` imports nothing else from Kiripix.
