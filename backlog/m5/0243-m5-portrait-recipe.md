---
status: todo
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0242-m5-portrait-asset-and-emotions.md, 0274-m5-set-colours-op.md]
---

# M5: the portrait's Stages: cutout, register, fit, palette, finish

Part of [0240](0240-m5-portrait-kind.md). Its table is the design, as the trial [0241](0241-m5-portrait-trial.md) left it.

## What to build

- **`cutout`:** the Prop's, run on the neutral image and on every picked emotion. A BiRefNet call is pinned per image.
- **`register`:** each emotion to the neutral, with the Looks' registration Op, outside the `face` region when there is one
  (a `face` Decision: a polygon or a brush, as the Looks' regions). Writes each emotion's transform and residual.
  `portrait.misaligned` is an error over half a target pixel, or when registration hits its limits, with an `owner_action` to
  re-make the edit.
- **`fit`:** one Grid transform from the neutral onto the canvas at the anchor, applied to every registered emotion. The alpha
  goes to the grid by majority vote.
- **`palette`:** the set's own colours, with [0274](0274-m5-set-colours-op.md)'s Ops: `mode=set` (default; `n`, `dither`,
  `keep` with the outline colour always kept), `project` (the Prop's strict mapping) or `off` (colours kept, only the alpha
  binary). Orphans removed per image. `palette.json` records the set's colours. The Check is "every pixel on the set's
  colours", not on the Project's (spec §2, principle 6's portrait exception).
- **`finish`:** the outline in `outline_colour`, and `lock_outside_face` if the trial asked for it in the first build.
  `portrait.shimmer` (info) reports, per emotion, the pixels outside `face` (or all of them, without one) that differ from
  the neutral's, with boxes.
- **Status:** a new emotion adds work only for that emotion where it can. A refit or a new palette rebuilds all of them. A
  `face` change puts `register` in needs-review.
- Long loops (per image, per emotion) check the cancel token.

## Acceptance criteria

- [ ] CLI seam, on a fixture set (a neutral and two emotions shifted and scaled by about 1 %, made in the test): after
      `finish`, every image is the canvas's size, the body outside the face is pixel-identical to the neutral's, and the
      residual is under half a pixel.
- [ ] An emotion shifted past the limits gives `portrait.misaligned`.
- [ ] `portrait.shimmer` counts a known change outside the face. Every pixel is on the set's colours, and the alpha is
      binary.
- [ ] Golden seam for any new Op. `uv run lint-imports` and `uv run mypy` pass.
