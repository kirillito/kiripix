---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0191-m4-ui-loops-screen.md, 0192-m4-frame-ops.md, 0193-m4-loop-kit-and-import.md, 0194-m4-loops-build-imported-frames.md]
---

# M4: frame Loops on the loops screen

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §11. It extends 0191's screen and preview.

## What to build

- **Source choice** for a `frames` Loop: Op, kit or edits (edits hidden if 0193's Part B was cut).
- **Op:** choose `sway`, `shimmer` or `scroll` and set its parameters with sliders. For `sway`, click the anchor row on the
  canvas. The preview updates as the sliders move. On a Plate Loop, `sway` is disabled with `loop.no_fill`'s message and a
  link to the layers screen.
- **Kit:** "Write kit" runs `loop kit` to a folder the Owner picks, then shows its path; "Import frames" takes the painted PNGs
  (file picker or drop).
- **Edits** (Part B): per frame, import and pick a Variant, as on the looks screen.
- **Frame strip:** the frames as thumbnails at ×4 nearest, frame 0 marked as the room's; click one to show it alone in the
  canvas, with onion skin of the previous frame at low opacity. Findings per frame (`loop.drift`, `loop.misaligned`,
  `loop.flicker`, `loop.outside_region`) are badges on the thumbnail.
- **Timing** per frame: a ticks field under each thumbnail, besides 0191's even timing and `pingpong`.

## Acceptance criteria

- [ ] Playwright against `kiripix serve`: a `sway` Loop on a Layer from the sliders; the preview plays and `loops.json` has
      it.
- [ ] Playwright: write a kit, import two frames from fixture PNGs, set a per-frame tick count; the strip shows them with a
      finding badge on the stray one.
- [ ] The Owner makes the kitchen's frame Loop in the time 0184 measured or less, timed and recorded here.

Budget: 150–250k tokens.
