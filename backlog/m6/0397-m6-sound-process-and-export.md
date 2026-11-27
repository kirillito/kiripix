---
status: todo
milestone: M6
agent: core-engineer + godot-export
type: ticket
parent: 0393-m6-sound-kind.md
---

# M6: process and export: trim, speed, loop, loudness, Godot

## What to build

- The `process` Stage, per Asset with per-Take overrides: `fade_in`, `fade_out` (ms), `speed` (tempo with pitch, as a
  sped-up splash), `pitch` alone, `highpass`, `lowpass`, `denoise` (light), mono or stereo, and the sub-kind's
  loudness target (two-pass `loudnorm` for LUFS targets, peak for SFX and UI).
- **Loops** (ambience, music): a loop point finder on a chosen window: the end matched to the start by
  cross-correlation, a short crossfade; `loop.seam` finding when the best match is poor.
- The `export` Stage: OGG Vorbis per the Project settings to `game/audio/<sub-kind>/<id>_<n>.ogg` and the Manifest
  entry with the source's provenance (URL, author, licence, the cuts and processing). No credit line: the game writes
  its own `CREDITS.md` from the Manifest (Owner, 2026-11-26); `audio.json` per 0394.
- Checks: a variation's length or loudness far from its siblings (`process.odd_one_out`); a looped file's seam.

## Acceptance criteria

- [ ] The asphalt recording: four picked Takes → four OGGs at peak −3 dBFS, mono, the Manifest entry carrying the
      source's URL, author and licence.
- [ ] The puddle recording: splashes sped up 1.5× and normalised; an ambience window looped with no click at the
      seam (the sheet shows it).
- [ ] Same inputs, same bytes.
