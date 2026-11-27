---
status: todo
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0393-m6-sound-kind.md
---

# M6: a contact sheet of a sound's Takes

## The gap

An agent reads images, not sound. A picture of the recording with its Takes marked lets it check a slice, and lets the
Owner see what was chosen before listening.

## What to build

- `kiripix sound-sheet <id> [--takes …] <out.png>`: the whole recording's waveform with each Take boxed and numbered,
  then one row per Take: waveform, a spectrogram (log frequency), and its numbers (length, peak, LUFS, centroid,
  clean rank). After `process`, the processed Take beside the source one.
- Small enough to read in one look (under ~1600 px wide); deterministic bytes.

## Acceptance criteria

- [ ] A sheet for the five-click fixture shows five boxes at the right places; a sheet of a processed Take shows the
      speed change and the loudness change in its numbers.
