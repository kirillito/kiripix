---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: `extend canvas --keep` per axis

Found in trial [0134](0134-m4-trial-room-extended-both-ways.md) (2026-11-16). The Owner keeps a quarter of the canvas on each
axis: 344 px across and 192 px down on a 1376 x 768 canvas. `--keep N` is one number for both axes
(`write_canvas`, `kiripix/core/extend.py`), so an east or a south canvas can match it, but a corner canvas can't: its two
strips need 344 and 192. In the trial the corner's `canvas.json` was edited by hand.

## What to build

- `--keep` takes one number (both axes, as today) or two, `--keep 344,192` (across, down). A one-sided canvas uses the axis
  across its join.
- Optionally, `[extend] keep` in `kiripix.toml` sets the default, so the Owner's quarter doesn't need typing each time. Today
  the default is a third. If added, it's a settings change: bump `schema_version` with a migration.
- `extend.keep_invalid` names the axis that doesn't fit.

## Acceptance criteria

- [x] CLI seam: `--keep 344,192` on an `east,south` corner writes strips of 344 and 192 px, and `canvas.json` records them.
- [x] `--keep 300` still keeps 300 on both axes.
- [x] The contract sample is updated if the output changes.

Budget: 30–60k tokens.

## Result (2026-11-16)

- `--keep` takes `N` or `ACROSS,DOWN` (`kiripix.core.extend.parse_keep`). A one-sided canvas uses only the axis across its
  join, so only the axes the canvas uses are checked; `extend.keep_invalid` names the axis (`across` or `down`) and the
  canvas extent it must fit, or says the text isn't one or two numbers.
- `[extend] keep` in `kiripix.toml` was not added (optional; it would need a settings migration). The default stays a third.
- The contract sample (`canvas --side east`) didn't need to change; it still passes.
- Tests: `tests/cli/test_extend.py` (`test_keep_per_axis_*`, `test_a_keep_that_does_not_fit_names_its_axis`).
