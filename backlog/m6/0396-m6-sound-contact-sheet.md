---
status: done
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

- [x] A sheet for the five-click fixture shows five boxes at the right places; a sheet of a processed Take shows the
      speed change and the loudness change in its numbers.

## Result

`kiripix sound-sheet <id> <out.png> [--takes 1,3,5-7]` (a Probe, in `kiripix/commands/sounds.py`; `commands/index.py`
regenerated). The drawing Ops are `kiripix/ops/sound_sheet.py` (`waveform_image`, `spectrogram_image`, `draw_box`,
`draw_column`, `span_columns`: pure numpy, uint8 RGB); layout, text (PIL's default font, as the cast sheet) and the
PNG are `kiripix/core/sound_sheet.py`. The PNG is 1500 px wide: the title, the whole recording's waveform with every
Take boxed and numbered (kept ones green, starred), a time ruler, then a row per Take (waveform with the onset marked,
log-frequency spectrogram in absolute dBFS, numbers). After `process`, the variation is drawn under its Take on the same
time scale, with its length ratio, peak and LUFS and their change, its non-default settings, and for a loop the seam
(pink columns, match and seam step). Bytes are the same on each run. No Stage changed, so no `version` bump.

Tests: `tests/golden/test_sound_sheet_drawing.py` (golden `sound_sheet_drawing.png`), `tests/cli/test_sound_sheet.py`, a sample in
`tests/cli/test_contract.py`.
