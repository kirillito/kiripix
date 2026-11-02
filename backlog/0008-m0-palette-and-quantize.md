---
status: review
milestone: M0
agent: imaging-engineer
type: ticket
parent: 0001-m0-skeleton.md
depends_on: [0003-m0-registry-and-contract.md]
---

# M0: palette and the quantise Op

Spec §7 (colour). User stories 45–51 of [0001](0001-m0-skeleton.md).

## What to build

- `ops`: `.gpl` load and save, `.hex` import, sRGB to OKLab, nearest colour (Euclidean in OKLab, ties broken by
  palette order), ordered Bayer 2/4/8 dithering in OKLab with a strength, and the conformance report. Pure numpy
  functions.
- `checks`: the palette Checks (`palette.duplicate_colour`, `palette.empty`, `palette.alpha`) and the image Checks
  (`image.partial_alpha`, and `palette.off_palette` with the count and the first positions).
- Commands `kiripix op quantize <in> <out> [--palette p] [--dither none|bayer2|bayer4|bayer8] [--strength s]` and
  `kiripix op conformance <image> [--palette p]`.

## Acceptance criteria

- [ ] Pixel-exact golden tests: strict mapping, each Bayer size, tie-breaking, transparent pixels, the partial-alpha
      refusal, an on-palette image unchanged, and a palette with duplicates.
