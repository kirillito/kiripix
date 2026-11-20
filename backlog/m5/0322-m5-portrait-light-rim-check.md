---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
---

# M5: a portrait's leftover white rim: a Check, and a cutout that takes it off whole

Found by [0241](0241-m5-portrait-trial.md), "The Owner's view", fault 1. The image model draws a white sticker rim round
the figure, and it is different in every image. `cutout`'s `remove_light_rim` ([0243](0243-m5-portrait-recipe.md)) takes
most of it, but pale grey-white specks stay on the silhouette's edge (hair strands, the hoodie's edge). They differ from
emotion to emotion, so they flicker when the expression changes. `key_fringe` and the near-white test both find 0 of them,
because the specks are grey, not white, and are on the edge.

## What to build

- **A Check, `portrait.light_rim`** (warning, on `finish` or `palette`): per emotion, the opaque pixels on the
  silhouette's edge (a transparent 4-neighbour) that are pale and grey, before the outline is drawn, with boxes. The
  fallback's `light_edge` (`0241-trial/portrait_set.py`: OKLab L over 0.75, chroma under 0.06) finds 2-4 per emotion on
  Sanjay's trial set. Calibrate the thresholds on that set, and check that the eye highlights and the white of the eyes
  aren't counted (they aren't on the edge).
- **The cutout takes the rim off whole:** try, on the trial's six images, clearing pale pixels on the edge after the outline
  is drawn, or a looser `remove_light_rim` (lower `lightness`, a little more `chroma`) that reaches these specks, or
  peeling one pixel off the alpha where it is pale. Pick the one that leaves the Check at 0 on all six without eating the
  hair's own highlights. Put it in a parameter of `cutout` or `finish`, on by default.
- If what `cutout` or `finish` writes changes, bump its `version` and name the bump in the Result.

## Acceptance criteria

- [x] Golden seam for a changed or new Op: a small figure with grey specks on its edge and a white highlight inside; the
      specks go and the highlight stays.
- [x] CLI seam: a fixture emotion with pale specks on its edge gives `portrait.light_rim` with the cleaning off, and none
      with it on.
- [x] On the trial's six images (`0241-trial/input/`), the Check finds 0 after the cleaning; recorded in the Result with
      a before and after crop at 4x.
- [x] A sample in `tests/cli/test_contract.py` for the new finding code. `uv run lint-imports` and `uv run mypy` pass.

## Result

Done 2026-11-19 in the main session (the ticket names `imaging-engineer`; the Owner asked for it in the main session's batch).

- **What the specks are:** run through the real Stages on the trial's six images (`fit` at 192 x 240, `head_top` 40), the
  white rim's leftovers are single pale pixels, or pairs, on the hair's left edge: 8-connected pieces of 1 or 2 px touching
  the silhouette's edge. The hair's and eyes' own highlights are pieces of 7 to 55 px inside the figure. Thresholds tried at
  L 0.75 / chroma 0.06, 0.7 / 0.08 and 0.65 / 0.08 found the same pixels.
- **Ops** (`kiripix/ops/chroma.py`): `light_edge(rgba, lightness=0.7, chroma=0.08, largest=4)`, a Mask of each piece of pale
  grey opaque pixels of at most `largest` px with a pixel on the edge (a transparent 4-neighbour; the canvas's border counts as
  figure, so the waist cut isn't an edge), and `clear_light_edge`, which clears those pieces whole. The first try, peeling
  pale edge pixels three times, cleared the six images too, but the CLI fixture showed it eats 3 px into any pale grey area on
  the edge (a white shirt); the piece-size limit leaves that alone.
- **Where:** `finish` runs it before the outline (`clear_light_edge`, a bool, on by default), and records per image what it
  cleared and what is left (`finish.json` `light_edge`). **`portrait.light_rim`** (warning, on `finish`): per image, the specks
  left, with boxes. With the cleaning off its `fix` is `kiripix set <asset> finish clear_light_edge=true`; with it on (only if
  a speck is larger than 4 px) an `owner_action` to judge by eye and widen the cutout's `rim_reach`.
- **Version:** `finish` 1 → 2, shared with 0321's bump.
- **The trial's six images, `portrait.light_rim` per image** (neutral, happy, sad, angry, surprised, worried): with the cleaning
  off 6, 1, 1, 2, 2, 2 px; with it on **0 on all six**. Before (top) and after (bottom), the hair's left edge at 4x:
  [0322-result/light_rim_before_after_4x.png](0322-result/light_rim_before_after_4x.png). One pale pixel stays in `happy`, 3 px
  inside the hair between two strands (L 0.77): it isn't on the edge, so neither the Check nor the cleaning touches it, and it
  is the same pixel in both rows. The Owner judges whether it flickers.
- **Tests:** golden `tests/golden/test_portrait_ops.py::test_pale_specks_on_the_edge_go_and_a_highlight_inside_stays`
  (`expected/portrait_light_edge.png`, new in LFS: specks go, one of them two deep; a highlight inside, a 9 px collar on the
  edge and white on the cut stay). CLI: `test_pale_specks_on_the_edge_are_a_light_rim_until_finish_clears_them`. The contract
  test lists the new code. `lint-imports` and `mypy` pass.
