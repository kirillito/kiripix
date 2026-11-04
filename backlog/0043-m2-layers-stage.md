---
status: todo
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0039-m2-chained-runner-calls.md, 0040-m2-inpainting-runner.md, 0042-m2-layer-ops.md]
---

# M2: the real `layers` Stage: lift, inpaint, grow

Spec §6.1, §7, §8 and ADR 0004. Stories 1–5, 7 and 8 of [0037](0037-m2-layers-and-props.md). Follows D1, D2, D4 and D10 in [0037](0037-m2-layers-and-props.md).

## What to build

- Replace `_layers` ([room.py:209](../kiripix/recipes/room.py#L209)). Upstream: `fit` first (the clicks' image), then `source`.
- A `click` Decision (`on_image`): `{layer, x, y, positive}` in target pixels. Grouping is as in `masks`, one Runner call per
  positive click plus the negative clicks right after it, and the Masks for one Layer ID are added together. Share
  `_click_groups` rather than copy it. A Layer ID matches `^[a-z0-9_]+$`, and `plate` is refused.
- Runner calls, through `SEGMENTER` and `INPAINTER` only: segmentation on the Source, capped as `masks` does; then one fill
  per connected hole, cropped around it, so a new object keeps the earlier objects' pinned results.
- Target-grid results: alpha through `mask_to_target`; `grow` applied (`ParamSpec`, default 1, minimum 0); the hole is the
  union of the grown alphas; the fill maps to the target the way `fit` maps the Source.
- D1's trim mechanism, with the journal replaying it in order.
- Output, flat in `work/layers/`: `plate.png`, `layer.<id>.png` for each Layer (the fit image cut by alpha),
  `foreground.png` (the Derived mask, 1-bit), and `layers.json` listing the Layers in order.
- Checks: `layers.recompose_mismatch` and `layers.plate_hole`, each with one of `fix` or `owner_action`. An Override outside
  a hole fails the first, and its `owner_action` says to paint on `fit`.
- With no Decisions: `plate.png` stays a byte copy of `fit.png`. Keep `image="plate.png"`.
- Check for cancel between Layers and fills. Update the `describe` text and the comment left at the Stage.

## Notes

- `masks` reads the Plate, so a lift puts its floods and clicks in `needs-review`. Its pinned Runner calls are keyed on the
  Source, so they stay valid. That's the spec's replay rule, not a bug.
- `palette` still reads the Plate only until [0045](0045-m2-palette-with-layers.md).
- An M1 gate finding, not in scope here: `room.harbor_front`'s `solid` exported as 1,533 convex collision pieces, from 68
  islands, 43 of them 4 px or smaller. Layers don't change collision, since a Layer's collision comes from `solid`.

## Acceptance criteria

- [ ] With fake Runners: a `click`, then one `run --rerun`, pins a segmentation and a fill and lands in `needs-review`;
      `accept` gives `done` with `plate.png`, `layer.<id>.png`, `foreground.png` and `layers.json`.
- [ ] Plate + Layers recompose exactly to the fit image, from the output files.
- [ ] `set layers grow=0` then `grow=2`: the alpha and the hole move together, only where partial, and fills go to "Runner
      input changed"; segmentation calls aren't re-run.
- [ ] Adding a second object in another part of the room makes one new segmentation and one new fill.
- [ ] A room built before this Stage, with floods and no layer Decisions: `layers` is stale, then `plate.png` is
      byte-identical to `fit.png`, and `masks` is not `needs-review`.
- [ ] A lift on a room with floods: `masks` goes to `needs-review` with no Runner call.
- [ ] Swapping the fake inpainter for one with another ID gives "Runner input changed", with no other change to the Stage.
- [ ] `plate` as a Layer ID is refused with `decision.invalid`.
