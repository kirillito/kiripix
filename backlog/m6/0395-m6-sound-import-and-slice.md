---
status: done
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
- `keep` Decision (ADR 0016; was `pick`): `kiripix decide <id> keep --takes 3,5,8,11` names the variations, in order, recorded by span (`start_ms`, `end_ms`).
- Findings: `slice.none` (nothing over the threshold), `slice.clipped` (a Take reaches 0 dBFS), `slice.overlap`.

## Acceptance criteria

- [x] CLI seam: the founder's asphalt recording (`backlog/m6/0398-trial/shoes-walk-road-asphalt-hard.flac`) slices into single steps; a fixture with five synthetic clicks gives
      five Takes at the right times (± 5 ms).
- [x] A chosen keep survives a re-slice with the same settings; a changed threshold that drops a kept Take is a
      finding, not a silent change.

## Result

- **The Kind.** `kiripix/recipes/sound.py`: `sound`, registered in `recipes/__init__.py`. Stages `source`, `slice`, `keep`, and
  `process` and `export` as declared stubs (no `run`: needs-input "not implemented until M6", `export` with `output_root = "out"`),
  so 0397 and 0400 fill in the Stage and its `run` and nothing else moves. Asset parameters `use` (required choice: sfx, ui,
  ambience, music) and `sound_id` (default `<prefix>.<name>`, read through `kiripix.core.sounds.sound_id`); `kiripix new sound <name>
  --use sfx --sound-id sfx.footstep.asphalt`. The Project check `sound.id_prefix` (owner action) is registered in
  `project_checks.py` (`check_sound_ids` in `core/sounds.py`). `sound.name_taken` is left to 0400.
- **Settings.** `[sound]` (`folder`, `rate`, `quality`) and `[sound.use.<use>]` (`prefix`, `channels`, `peak`, or `lufs`, `true_peak`,
  `lra`) in `kiripix/core/settings.py` (`SoundSettings`, `SoundUse`); a use the file leaves out has the game's row. `kiripix.toml`
  `schema_version` 14 to 15, no-op migration `_add_sound_section` (the defaults are read, written nowhere). `init`'s template has the
  tables and four LFS rules (`*.wav`, `*.flac`, `*.mp3`, `*.ogg`). A row with both targets, none or part of a loudness target is
  `settings.sound_target`. Tests that named schema 14 now say 15.
- **ffmpeg.** `imageio-ffmpeg==0.8.1` added with `uv add` (`pyproject.toml`, `uv.lock`; a mypy override, since it has no stubs).
  `kiripix/recipes/ffmpeg.py` is the only place that runs it: `executable()` (refuses another wheel version or a binary outside the
  wheel: `ffmpeg.wrong_version`, fix `uv sync`), `version_line()` as the computed Stage input `ffmpeg.version` (in `source`'s
  `settings`), `run`, `probe`, `decode_to_wav`, `decode`. A cancel kills the process. `kiripix/recipes/wav.py` reads and writes
  float WAVs (`read_wav`, `write_wav`).
- **import.** `kiripix import <id> <file> [--url] [--author] [--licence]` for a sound: the file is probed (decoded whole) by ffmpeg, then
  stored whole as `src/<hash16>.<ext>`; `import.not_a_sound` (extension), `import.not_audio` (ffmpeg can't read it),
  `import.sound_takes_a_recording`, `import.provenance_needs_sound`. Provenance is on the file's line in `imported.jsonl`, which is now
  `schema_version` 3 (`url`, `author`, `licence`, `at`; version 1 and 2 lines read as before). The same bytes again with flags add a
  newer line and no Variant; a flag left out keeps what the newest line (by `at`) had. `ImportData.sound` returns the rate, channels,
  duration, codec and Provenance. `source` and `slice` don't read `imported.jsonl`, so a correction makes no Stage stale.
- **slice.** `kiripix/ops/sound.py` (pure numpy): `find_takes` (frame level and spectral flux, both in dB, so one `threshold` serves
  both; `min_gap`; the onset located to the sample; the end where the level falls `floor` dB under the Take's early peak, or within
  6 dB of the recording's background, at the latest `tail` ms after the onset and at the latest where the next Take starts),
  `find_whole`, `measure_take` (peak, RMS, BS.1770 integrated LUFS, spectral centroid, tail level, clipped), `lufs` (checked against
  ffmpeg's `ebur128`: -21.66 against -21.7), `similarity_to_median`, `clean_ranks`. Parameters: `mode` (auto), `threshold` 12 dB,
  `min_gap` 120 ms, `pre_roll` 10 ms, `tail` 1500 ms, `floor` 30 dB. A Take under 400 ms has no BS.1770 block: its LUFS is the mean
  square over the Take. Findings: `slice.none` (error, fix `set ... slice threshold=<lower>`), `slice.clipped` (warning, peak at or over
  -0.1 dBFS), `slice.overlap` (warning).
- **keep.** The `keep` Decision `{"takes": [{"start_ms", "end_ms"}, ...]}` (latest counts); `kiripix decide <id> keep --takes 3,5,8,11`
  writes it from the numbers (refused for a `slice` that isn't `done`: `keep.slice_not_done`, an unknown number `keep.take_unknown`).
  Replay as in ADR 0016: exact within 1 ms is `done`; a moved bound is needs-review through the Stage's `review` hook, and `accept`
  re-records the new spans; missing or split is needs-input with `keep.take_missing` or `keep.take_split`, naming the Take and its span
  (`data`: `take`, `start_ms`, `end_ms`, `problems`). A Take that has run together with an earlier kept one is `keep.take_missing`.
  `keep.take_split` can't be reached with the fixtures (two Takes that both start within 15 ms of a span and each cover half of it need
  a span under 30 ms), so only the code path exists, untested.
- **`kiripix sound-takes <id>`** (probe, MCP exposed): a table, or JSON with every measure, the `slice` settings, `slice_status` and
  each Take's `kept` variation number. Index regenerated (`commands/sounds.py`).
- **Stage `version` bumps:** none. Every Stage is new.
- **Tests:** `tests/cli/test_sound.py` (fixtures are generated in the test with numpy, `wave` and the wheel's ffmpeg); a sample for
  `sound-takes` and a schema test for the sound's `import`, `decide --takes` and `show` in `test_contract.py`.
- **The founder's recording** (`shoes-walk-road-asphalt-hard.flac`, 9.0 s, mono, 48 kHz): 15 Takes by default (`threshold` 12):
  onsets (ms) 720, 1377, 1934, 2524, 3122, 3710, 4328, 4929, 5203, 5484, 6022, 6582, 7096, 7622, 8191, each 50 to 500 ms long, a step
  about every 0.6 s. Take 9 (5203 ms, -28 dBFS) is a faint scuff between two steps; `threshold=15` drops it. Takes 13 (498 ms) and 15
  (396 ms) are long and score a likeness of 0.37 and 0.42 against 0.6 to 0.95 for the rest: a scrape or a slide.
- **Not verified:** the Linux wheel (no Linux machine here). On Windows the wheel's ffmpeg 9.0.2 decodes WAV, FLAC, MP3 and OGG;
  `docs/versions.md` says so, and that the bundled binary is a GPL build, a dev-time tool that ships nothing to the game.
- **For the next tickets:** decode with `kiripix.recipes.ffmpeg.decode(path, check_cancel)` (rate, float32 (frames, channels)) or read a
  Stage's own `work/source/source.wav` with `recipes.wav.read_wav`. `work/source/source.json` holds the Variant, rate, channels, frames.
  `work/slice/takes.json` (`TakesRecord`, `schema_version` 1): `rate`, `channels`, `frames`, `duration_ms`, `mode`, `settings`, and
  `takes` each with `number`, `start_sample`, `onset_sample`, `end_sample` (exclusive), `start_ms`, `onset_ms`, `end_ms`, `peak_dbfs`,
  `rms_dbfs`, `lufs`, `centroid_hz`, `similarity`, `clean_rank`, `tail_dbfs`, `clipped`, `overlaps_next`. `work/keep/keep.json`
  (`KeepRecord`): `kept` in variation order, each `variation`, `take`, `start_sample`, `end_sample`, `start_ms`, `end_ms`, as `slice`
  has them now. `kiripix.recipes.sound` has `read_takes`, `match_takes` (what a `process` Decision naming a Take by span reuses),
  `latest_keep`, `kept_spans`, and the Kind's `USES`; `kiripix.core.sounds` has `takes_view`, `sound_id`, `provenance` (the newest
  Provenance of a stored recording: 0400 reads it for `sound.provenance_missing` and the Manifest's `source`), `keep_document`.
  `process` and `export` list `ffmpeg.version` and a `sound` setting (a Stage's `settings` names are static, so the whole `[sound]` table, not one use's row) in `StageInputs.settings`.
