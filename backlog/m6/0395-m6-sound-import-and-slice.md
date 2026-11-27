---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0393-m6-sound-kind.md
---

# M6: import a recording and slice it into Takes

## The gap

A recording of footsteps holds a dozen steps; one of a puddle holds splashes run together. An agent can't hear where
one ends, so it guesses from numbers.

## What to build

- `kiripix import <id> <file>` for a `sound` Asset: WAV, FLAC, MP3, OGG; with `--url`, `--author`, `--licence`.
- The `slice` Stage: onset detection (energy and spectral flux, tunable `threshold`, `min_gap`, `pre_roll`,
  `tail` until the level falls under a floor) gives **Takes**: start, end, peak dBFS, integrated LUFS, RMS, spectral
  centroid, and a similarity score to the median Take (a step that is really a scrape scores low).
- `kiripix sound-takes <id>` prints them as a table; JSON for agents. A Take ranked by how clean it is (no overlap
  with the next one, no clipping, a quiet tail).
- `pick` Decision: `kiripix decide <id> pick --takes 3,5,8,11` names the variations, in order.
- Findings: `slice.none` (nothing over the threshold), `slice.clipped` (a Take reaches 0 dBFS), `slice.overlap`.

## Acceptance criteria

- [ ] CLI seam: the founder's asphalt recording slices into single steps; a fixture with five synthetic clicks gives
      five Takes at the right times (± 5 ms).
- [ ] A chosen pick survives a re-slice with the same settings; a changed threshold that drops a picked Take is a
      finding, not a silent change.
