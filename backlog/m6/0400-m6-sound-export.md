---
status: done
milestone: M6
agent: godot-export
type: ticket
parent: 0393-m6-sound-kind.md
---

# M6: export a sound to Godot, with its provenance in the Manifest

Split from the first 0397 (Owner, 2026-11-27). Needs [0397](0397-m6-sound-process-and-export.md)'s processed Takes.

## What to build

- The `export` Stage: OGG Vorbis per the Project settings to `<[sound] folder>/<use>/<name>[_<n>].ogg` (`_<n>` only when several, ADR 0016) and the Manifest
  entry with the source's provenance (URL, author, licence, the cuts and processing).
- No credit line and no `audio.json`: the game writes its own `CREDITS.md` and keeps its own `audio.json` from the
  Manifest (Owner, 2026-11-26 and 2026-11-27; ADR from 0394).

## Acceptance criteria

- [x] The asphalt recording: four picked Takes → four OGGs at peak −3 dBFS, mono, the Manifest entry carrying the
      source's URL, author and licence.
- [x] Same inputs, same bytes.

## Result

Built the `export` Stage and the Exporter's sound handling.

- **Stage `version` 2** (the stub had no output; nothing to bump elsewhere). `kiripix/recipes/sound.py`: `_export` encodes each
  `process` variation with `ffmpeg.encode_ogg` (new in `kiripix/recipes/ffmpeg.py`: `-c:a libvorbis -q:a <quality> -ar <rate>`
  and `_BITEXACT`), decodes the OGG again and measures peak, LUFS and length of what the game will play, and writes
  `<name>[_<n>].ogg` and `sound.json` (`SoundRecord`, schema 1). Inputs: `source` and `process`, `imported.jsonl`, and the
  settings `ffmpeg.version` and `sound`. `<name>` is `file_stem(sound_id, prefix)`; a `sound_id` whose stem has anything but
  letters, digits, `_` and `-` fails the Stage (`sound.id_invalid`) so a name can't leave the folder.
- **Determinism, found by trying it**: two encodes are byte-identical with `-fflags +bitexact -flags:a +bitexact`. Without them
  the Ogg stream serial is random (each run differs); with them it is 0. The `Lavc` tag stays but is fixed. Threads are one.
  The measured peak of an encoded file is up to about 1 dB under the target (Vorbis is lossy and the noise bursts of the test
  fixture lose their top): `peak_dbfs` in the Manifest is the encoded file's, not the target.
- **Provenance**: `read_provenance` (recipes) reads `imported.jsonl` (newest `at` wins); `core.sounds.provenance` now calls it.
  `sound.provenance_missing` is a Stage Check (error, `owner_action`), so `check` and `export` refuse with exit 2.
- **Manifest schema 5** (`kiripix/export/manifest.py`): optional `sound` block (`SoundEntry`); `migrate_v4`; a schema 4 Manifest
  is read as having none and rewritten once. A `None` (`loop_offset`, an unset `url`) is left out of the file, as every None is.
  Every Kind's Manifest is now written as schema 5 (the existing tests' `== 4` became `== 5`).
- **Exporter** (`kiripix/export/sound.py`, `__init__.py`): files to `<[sound] folder>/<use>/` through the same plan, ownership,
  `--force`, `--adopt` and backups; the counter counts a changed `sound` block too, and `export_pending` compares it, so a
  corrected Provenance makes `export` offer itself. `GodotTarget.sound_folder`; a folder outside the game is
  `export.bad_sound_folder` (asked only for a sound, so no other Kind is stopped). `export_stamp` scans the sound folder too.
- **Prune** takes files inside the sound folder only from a Manifest with a `sound` block; sidecars (`.ogg.import`) go with
  their file and the emptied use folder goes. **Merge**: our `sound` block (theirs when only theirs has one).
  **`manifest install`** writes `*.ogg merge=kiripix-ours` into `<sound folder>/.gitattributes`; `export` warns
  (`export.merge_driver_missing`) about a missing rule only when the sound folder exists.
- **Freeze**: `export.id_frozen` for `sound_id` and `use` (`frozen_findings`). `sound.name_taken` is a Project check in
  `core.sounds` (exact same stem in one use; `x` against `x_2` is caught at export as an unmanaged file).
- Kiripix writes no `audio.json` and no `CREDITS.md`.
- Tests: `tests/cli/test_export_sound.py` (synthetic; the asphalt recording when present).
