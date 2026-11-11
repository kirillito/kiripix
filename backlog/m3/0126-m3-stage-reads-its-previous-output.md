---
status: done
milestone: M3
agent: core-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0099-m3-core-for-characters.md]
---

# M3: a Stage can read its own previous output

Spec §6.3 (render) and §10. Split out of [0119](0119-m3-render-keeps-unchanged-clips.md), which stops without it. A Stage builds
into a fresh temporary folder that core swaps into place whole. While it runs, the old `work/<stage>/` is still on disk, but
only core knows its path. So `render` can't copy the frames of clips that didn't change, and adding one clip renders about 770
frames again.

## What to build

- `StageRun` (`kiripix/recipes/base.py`) gains `previous: Path | None`. Core sets it to the Stage's current output folder when
  that folder exists and holds its stamp. Otherwise it is None (first build, or the folder is missing or half-made).
- It is read-only for the Stage. The Stage copies from it into `output_dir` and never writes to it. Core still swaps the new
  folder in whole, so a cancel or a failure leaves the old output as it was.
- `previous` is set whether or not the stamp's input hash matches. A Stage that reuses its old output checks its own
  finer-grained keys (0119 keys each clip and direction). Say so in the docstring.
- `previous` is not an input. It never enters a hash, and a Stage that ignores it behaves as now.

## Acceptance criteria

- [ ] CLI seam with the test Kind `demo`: a test Stage that copies a file from `previous` sees None on the first build and
      the last build's folder on a rebuild. Its writes to `previous` are refused, or at least don't survive the swap. A
      cancelled rebuild leaves the old output byte-equal.
- [ ] `mypy` and `lint-imports` pass. `recipes` still doesn't import `core`.

Budget: 30–60k tokens.
