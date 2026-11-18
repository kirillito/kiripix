---
status: todo
milestone: M5
agent: core-engineer
type: ticket
---

# M5: a portrait's per-emotion images in `show`, and a `face` change puts `register` in needs-review

Left by the 2026-11-18 batch review of [0243](0243-m5-portrait-recipe.md) and [0245](0245-m5-ui-portrait-screens.md).

## What to build

- **Each emotion's built images in `show`**, per Stage, as `StateOut.images` does for a Prop's state (`stage`, `image`,
  `input_image`). The UI builds `<stage>/emotions/<id>.png` from the Stage's `image` today (`emotionImage` in
  `web/src/portraitScreens.tsx`) and learns whether it exists only when it loads.
- **A `face` change puts `register` in needs-review**, as 0243 asks. As built, `face` is `on_image`, so a new neutral cutout
  does it, and a `face` edit only makes `register` stale. Decide with the Owner whether the review is still wanted (the UI reruns
  `register` after each stroke, so the Owner sees the result anyway); if not, change 0243's line instead.

## Acceptance criteria

- [ ] CLI seam: `show` of a built portrait lists each emotion's image per Stage; contract sample updated.
- [ ] The `face` rule decided and tested at the CLI seam.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
