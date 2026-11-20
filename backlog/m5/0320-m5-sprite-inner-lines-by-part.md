---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0234-m5-sprite-style-and-size-trial.md
---

Built after [0319](0319-m5-sprite-palette-by-parts.md), whose parts it draws between.

# M5: inner lines on a sprite, where two parts meet

Found by [0234](0234-m5-sprite-style-and-size-trial.md): a body has a 1 px line at the borders between its Model's materials
(`finish inner_lines`, `outline` or `dark`); a PixelLab sprite has none, or its own soft one, so it reads softer beside them.

## What to build

- `finish`'s `inner_lines` and `line_skip` for a sprite, on the borders between the parts of [0319](0319-m5-sprite-palette-by-parts.md)
  instead of materials: the line on the farther pixel of each border, as for a body (for a sprite, "farther" is the lower
  part in the frame unless a better rule shows itself), with the same `outline` and `dark` choices.
- Nothing changes for a sprite without parts. Bump `finish`'s `version`.

## Acceptance criteria

- [x] Golden test on the Op: two parts meeting, a 1 px line on the border, none round a part that `line_skip` names.
- [x] 0234's worker with lines, beside the bodies at 1x and 4x.

## Result (2026-11-19)

- The sprite's `finish` reads the material pass that `palette` writes for its parts (0319). Each part's regions are joined
  into one, so a line runs between parts, not between the regions of one part. A region in no part is a part of its own.
  `line_skip` and `finish.json` name the parts. A sprite has no depth pass, so every pixel ties and the line is the lower
  pixel of a border (the right one, side by side). It has no mask either, so its alpha is the inside, and `line_depth` does
  nothing. `outline` and `dark` work as for a body (`dark` with parts needs `part_lines`, as a body's does).
- A sprite with no `parts` and `inner_lines` on now fails with `finish.inner_lines_without_parts` (fix
  `finish inner_lines=off`). Before, it failed with no clear message. Nothing changes for a sprite with lines off.
- **`finish`'s `version` is bumped** to the character's + 1 (5) on the sprite Recipe.
- Tests: golden `test_an_inner_line_where_two_parts_meet_and_none_round_a_skipped_part` (new image
  `sprite_parts_inner_lines.png`) and CLI `test_finish_draws_inner_lines_where_a_sprites_parts_meet`.
- The worker with `inner_lines=outline`, as the bodies have: the third row of
  [worker_parts_lines_4x.png](0319-trial/worker_parts_lines_4x.png) and
  [worker_parts_lines_s_x5.png](0319-trial/worker_parts_lines_s_x5.png).
