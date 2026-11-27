---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0393-m6-sound-kind.md
---

# M6: process a sound: trim, speed, loop, loudness

Split from the first 0397 (Owner, 2026-11-27): this ticket is the `process` Stage; the `export` Stage and the Manifest
entry are [0400](0400-m6-sound-export.md) (godot-export). The audio engine is ffmpeg, pinned through the
`imageio-ffmpeg` wheel in `uv.lock` (ADR from 0394).

## What to build

- The `process` Stage, per Asset with per-Take overrides: `fade_in`, `fade_out` (ms), `speed` (tempo with pitch, as a
  sped-up splash), `pitch` alone, `highpass`, `lowpass`, `denoise` (light), mono or stereo, and the sub-kind's
  loudness target (two-pass `loudnorm` for LUFS targets, peak for SFX and UI).
- **Loops** (ambience, music): a loop point finder on a chosen window: the end matched to the start by
  cross-correlation, a short crossfade; `loop.seam` finding when the best match is poor.
- Checks: a variation's length or loudness far from its siblings (`process.odd_one_out`); a looped file's seam.

## Acceptance criteria

- [x] The asphalt recording (`backlog/m6/0398-trial/shoes-walk-road-asphalt-hard.flac`): four picked Takes → four
      processed Takes at peak −3 dBFS, mono.
- [x] The puddle recording (`backlog/m6/0398-trial/puddle-footsteps.wav`): splashes sped up 1.5× and normalised; an
      ambience window looped with no click at the seam (the sheet, 0396, shows it).
- [x] Same inputs, same bytes.

## Result

Built the `process` Stage of the sound Recipe (`kiripix/recipes/sound.py`), in a new Stage `version` 1 (nothing to bump: the
stub had no output).

- **Parameters** (Asset level, `kiripix set <id> process k=v`): `trim_start`, `trim_end`, `fade_in` (2 ms), `fade_out`
  (10 ms), `speed` (tempo and pitch together, `asetrate`), `pitch` (semitones, rubberband), `highpass`, `lowpass`, `denoise`
  (afftdn, dB), `channels` (0: the use's row), `loop` (auto: ambience and music), `loop_start`, `loop_end`, `loop_crossfade`
  (50 ms), `loop_search` (1000 ms), `loop_min_match` (0.2). Per-Take overrides are the `tune` Decision
  (`decide <id> process --decision '{"decision":"tune","data":{"start_ms":..,"end_ms":..,"speed":1.5}}'`), matched to a kept
  Take with `match_takes`. No new Command: `set` and `decide` are generic.
- **Loudness**: peak for a `peak` row (numpy, exact); two-pass `loudnorm` (linear) for a LUFS row, through
  `ffmpeg.measure_loudness` and `ffmpeg.apply_loudness`. Every ffmpeg run uses `-fflags +bitexact -flags:a +bitexact
  -map_metadata -1 -threads 1 -filter_threads 1`; the WAVs are written by `wav.write_wav`.
- **Loops**: `ops.find_loop_end` (normalised FFT cross-correlation of the crossfade's length before the start against each
  candidate end), `ops.crossfade_loop` (equal-power for a poor match, linear for 0.5 or more), `ops.seam_step`.
- **Checks**: `process.odd_one_out` (3 or more variations; length 2x from the median or 6 LU from its loudness),
  `process.loop_seam` (best match under `loop_min_match`; fix doubles `loop_crossfade`, or an owner action past 2.5 s),
  `process.override_unmatched` (a `tune` that names no kept Take). All warnings.
- **Output**: `<n>.wav` (44.1 kHz float32) and `process.json` (`ProcessRecord`, schema 1, in `kiripix.recipes.sound`).
- Tests: `tests/cli/test_sound_process.py` (synthetic; the asphalt and puddle recordings when present).

Deferred: a `gain` trim after loudness; a true-peak check of a peak row; a `loudnorm` that falls back to dynamic mode is not
reported (the result's LUFS in `process.json` shows it).
