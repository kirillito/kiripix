---
status: done
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

- [x] CLI seam: `show` of a built portrait lists each emotion's image per Stage; contract sample updated.
- [x] The `face` rule decided and tested at the CLI seam.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

- **`show` per-emotion images:** each entry of `data.emotions` has `images`: a list of `{stage, image, input_image}` (the same
  shape as a Prop state's `StateOut.images`), one per Stage that has an image and that has the emotion's file
  (`<stage>/emotions/<id>.png`) as its own output (`image`) or as the input it is made from (`input_image`). Either may be null;
  a Stage with neither isn't listed. `kiripix/commands/show.py` (`_emotion_images`). No Stage `version` bump.
- **The `face` rule (Owner's decision, 2026-11-18): stale only.** A `face` edit makes `register` and what follows stale, and does
  not put `register` in needs-review: the UI reruns `register` after each stroke, and the portrait is being redesigned around
  whole-body emotions (0241). 0243's line was changed to say so. Pinned by
  `test_a_face_edit_makes_register_stale_and_not_needs_review` in `tests/cli/test_portrait_stages.py`.
- Tests: `test_show_lists_each_emotions_built_images_per_stage` (same file); the contract sample in
  `tests/cli/test_contract.py` (`test_a_portraits_emotions_validate`) checks `images` is present.
