---
status: todo
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
  `face` change puts `register` in needs-review.
- Long loops (per image, per emotion) check the cancel token.

## Acceptance criteria

- [ ] CLI seam, on a fixture set (a neutral and two emotions shifted and scaled by about 1 %, made in the test): after
      `finish`, every image is the canvas's size, the body outside the face is pixel-identical to the neutral's, and the
      residual is under half a pixel.
- [ ] An emotion shifted past the limits gives `portrait.misaligned`.
- [ ] A fixture whose emotions differ only by noise outside the face: with the lock, the body outside the face is the
      neutral's exactly; without it, `portrait.shimmer` counts the noise.
- [ ] `portrait.shimmer` counts a known change outside the face. Every pixel is on the set's colours, and the alpha is
      binary.
- [ ] Golden seam for any new Op. `uv run lint-imports` and `uv run mypy` pass.
