# A sound is an Asset of Kind `sound`, cut into Takes and processed with a pinned ffmpeg

**Status: proposed** (drafted 2026-11-27 for ticket 0394, from the Owner's decisions of 2026-11-26 and 2026-11-27, which
are recorded here as decided. On 2026-11-27 the Owner also confirmed `keep` (an agent may record it), the `res://audio` folder outside the export root, a lone variation with no number, and audio in git LFS.)

The game cuts its sound effects by hand today: an agent that can't listen guesses cut points from ffmpeg's numbers, and
most of an audio ticket's tokens go there (0393). The game's `audio` skill already fixes the files (OGG Vorbis, 44.1 kHz,
q5), the loudness targets and the IDs, and its `tools/audio_normalize` does the processing with ffmpeg. Kiripix has the
Manifest, the review queue and the Owner's approval of Provider calls, so sounds come here, as a Kind. Every Kind so far
is an image, so this ADR says what of the Stage graph, the Manifest and export a sound uses unchanged, and what it adds.

We considered:

1. **A separate tool beside the game.** It would need its own provenance record, review and approval, the expensive
   parts Kiripix already has.
2. **Four Kinds** (`sfx`, `ui`, `ambience`, `music`). Their Stages are the same and only their numbers differ (target,
   channels, whether it loops). Four Recipes would repeat each other, and reusing a click as an effect would mean a new
   Asset.
3. **One Kind, `sound`, with its use as an Asset parameter.** Chosen.

## The decisions

1. **Recipe: source → slice → keep → process → export.** The Owner's proposal, with `pick` renamed `keep`. A Pick is
   the Decision choosing one Variant as the Source, and a sound has one of those too (its recording), with `kiripix
   pick` as its Command. A second "pick" on the same Asset would be ambiguous in `show`, `next` and the UI.
   - **source:** the recording, imported as a Variant (`import <id> <file>`: WAV, FLAC, MP3 or OGG, stored whole in
     `src/`, in LFS) and picked as any Source is. One recording per Asset. The Stage decodes it to 44.1 kHz float PCM,
     keeping its channels. A raw recording never goes to the game.
   - **slice:** deterministic, no Decision. It finds the Takes (glossary) and measures each one. `mode` is `onsets`
     (energy and spectral flux) or `whole` (one Take: the recording less its silent head and tail). The default `auto`
     means `onsets` for `sfx` and `ui`, and `whole` for `ambience` and `music`.
   - **keep:** `needs-input` until a `keep` Decision names the kept Takes in order. The order gives the variation numbers
     1, 2, … . It's a Stage of its own because the choice is made after looking at `slice`'s output, and a Stage can't
     need its own Decision to build what that Decision is made on. An agent may record it: the choice is mostly
     measurable (clean rank, overlap, clipping, similarity), and the Owner can replace it. This isn't a Pick among
     Variants.
   - **process:** trim, fades, speed, pitch, filters, light denoise, channels, loudness and loops, per Asset, with
     per-Take overrides as `process` Decisions that name a Take the way `keep` does. It writes one file per variation
     in its output folder (`<n>.wav`, 44.1 kHz float, the use's channels, loudness applied) and `process.json` (per
     variation: the Take, length, peak, loudness, `loop`, `loop_offset`, the settings applied). The contact sheet
     (0396) and the UI play these files.
   - **export:** encodes each variation to OGG Vorbis and measures the result. It leaves `<name>_<n>.ogg` and
     `sound.json` (Kiripix's own, for the Exporter) in `out/export/`, as the icon's and portrait's `export` Stages do.
2. **The use is an Asset parameter.** `use` is `sfx`, `ui`, `ambience` or `music`, set at `new`. It picks the
   use's row of settings and the export folder. Adding a use is a code change.
3. **The sound's game ID is an Asset parameter too.** The Asset ID stays `sound.<name>` (one folder per Asset, as for
   every Kind). `sound_id` is the game's ID: `sfx.footstep.asphalt`, `amb.<place>.<name>`, `music.<name>`. It must start
   with the use's prefix (`sfx`, `ui`, `amb`, `music`), or `check` reports `sound.id_prefix`. It defaults to
   `<prefix>.<name>`. The file name is `sound_id` without its prefix, with dots as underscores
   (`sfx.footstep.asphalt` → `footstep_asphalt`), and several variations end `_1`, `_2`, …; a lone one has no number (`bedroom_room_tone.ogg`), as in the game's audio skill (Owner, 2026-11-27).
   `sound_id` and `use` are frozen once exported (`export.id_frozen`). Two sounds of one use that would get the same
   file name are refused (`sound.name_taken`, a Project check).
4. **A Take is identified by its span, not its number.** A `keep` or `process` Decision records each Take as
   `start_ms` and `end_ms` in the source. The number `slice` shows is only for typing (`--takes 3,5,8,11`), because a
   new threshold that finds an extra Take earlier renumbers everything after it. On replay, a recorded Take matches the
   one current Take whose start is within 15 ms of its start and that covers at least half of its span. Then:
   - every Take matches, each bound within 1 ms: the replay is exact, and the Stage is `done`;
   - every Take matches, but a bound moved further (a changed `tail`): `needs-review`, as a replayed click is. The
     Owner listens, and `accept` re-records the new spans;
   - a Take matches nothing (`keep.take_missing`) or two (`keep.take_split`): `needs-input`, naming the Take and its
     span. The Stage never drops a Take, renumbers the variations or picks a neighbour silently.

   The cut itself always comes from `slice` as it is now, sample-exact. The Decision only says which Take it is.
5. **ffmpeg is the audio engine, pinned through `uv.lock`.** It comes from the `imageio-ffmpeg==0.8.1` wheel, which
   bundles ffmpeg 9.0.2 with libvorbis, `loudnorm`, `afftdn`, `rubberband` and `atempo` (verified on Windows). We chose
   it over soundfile and numpy alone for output quality (denoise, tempo and pitch, a Vorbis encoder), and because the
   game's `tools/audio_normalize`, which the Owner calibrated the targets with, uses ffmpeg's `loudnorm`. A system
   ffmpeg, as the game uses, differs from machine to machine. ffmpeg calls are deterministic work, not Runner calls.
   They rebuild implicitly, as a Blender render does (ADR 0010). The first line of `ffmpeg -version` is a computed
   input (`ffmpeg.version`) of every Stage that runs ffmpeg, so a lock update makes them stale.
6. **Where ffmpeg lives under the import rule.** Ops stay pure numpy. ffmpeg is a subprocess, so it lives in one helper
   in `recipes`, `kiripix/recipes/ffmpeg.py`, as `blender_launcher.py` does for Blender. The helper finds the bundled
   binary, refuses another version (`ffmpeg.wrong_version`, `fix` `uv sync`), declares `ffmpeg.version`, and decodes
   to numpy or runs a filter graph into a file in the Stage's output folder. It kills ffmpeg when the Command is
   cancelled. The Stages use it, and so does core (which sits on `recipes`) for `import`'s probe and the contact sheet.
   `export`, `commands`, `cli` and `server` never run ffmpeg. The Exporter copies the `export` Stage's OGG bytes.
   Analysis is Ops over the decoded PCM: onsets, peak, RMS, BS.1770 loudness, spectral centroid, similarity to the
   median Take, the loop finder's cross-correlation, and the waveform and spectrogram images. Where numpy can do a step
   exactly it is an Op. ffmpeg does what needs its filters: decoding, resampling, `loudnorm`, `afftdn`, `rubberband`,
   `atempo` and the Vorbis encoder.
7. **The loudness and format table is Project settings.** `[sound]` in `kiripix.toml` holds `folder`, `rate` and
   `quality`, and `[sound.use.<use>]` holds `prefix`, `channels`, and either `peak` (dBFS) or `lufs`, `true_peak` and
   `lra`, seeded from the game's skill. A use row with both or neither is `settings.sound_target`. It's a new table, so
   `kiripix.toml`'s `schema_version` goes up by one, with a migration in `kiripix/core/settings.py` that adds nothing,
   since the defaults are read (as with `[inbox]` and `[providers]`). The Stages that use a row list it in
   `StageInputs.settings`, so a change to a target makes those sounds stale.
8. **Provenance is recorded at import, per file.** `import <id> <file> --url … --author … --licence …` writes them on
   the file's line in `imported.jsonl`. Importing the same bytes again with these flags adds a newer line and no
   Variant. The latest line by its time wins, since the file is `merge=union`. They describe the file, so they follow
   whichever recording is the Source. A correction makes only `export` stale: `export` reads `imported.jsonl`, but
   `source` and `slice` don't. Kiripix stores the licence as text and never interprets it, as it doesn't a Condition.
   A Source with no `author` or `licence` is `sound.provenance_missing` at `export` (an error, with an `owner_action`:
   only the Owner confirms a licence on the sound's own page). A generated sound's provenance (0399) comes from its
   Provider call.
9. **Export writes only the OGGs and the Manifest entry** (Owner, 2026-11-26 and 2026-11-27). Kiripix never writes the
   game's `game/data/audio.json` or `CREDITS.md`. The game builds both from the Manifest, and `audio.json` holds the
   game's own mixing (`bus`, `volume_db`, `pitch_jitter`). The files go to `<folder>/<use>/<name>_<n>.ogg`, where
   `[sound] folder` is `res://audio` (the game's `game/audio/`). That folder is outside `[export.godot] root`, so the
   spec's rule that everything Kiripix writes goes under the root gains this one exception. The Manifest itself stays
   under the root (ADR 0003 is unchanged), and ownership, `--force`, `--adopt` and `--prune` apply to these files as to
   any other. An OGG the game made by hand at the same path needs `--adopt`. The Manifest gains an optional `sound`
   block: `id`, `use`, `files` in variation order (each `path`, `take` with `start_ms` and `end_ms`, `length_s`,
   `peak_dbfs`, `lufs`, `loop`, `loop_offset`), `source` (file name, hash, `url`, `author`, `licence`) and `processing`
   (the settings applied). This is the Manifest's schema 5. A schema 4 Manifest is read as having no `sound` block and
   is rewritten once at its next export, as with 3 and 4. The merge driver takes our `sound` block with our `files`.
10. **Determinism.** What is promised: the same inputs give the same OGG bytes on the same platform (Windows x86-64, or
    Linux x86-64) with the locked `imageio-ffmpeg` wheel. The encode runs with fixed flags: `-fflags +bitexact
    -flags:a +bitexact` (no encoder tag, and a fixed Ogg stream serial in place of a random one), `-map_metadata -1`,
    `-threads 1`, `-c:a libvorbis -q:a <quality> -ar <rate>`. Decoding FLAC and WAV is bit-exact everywhere. MP3 and
    OGG decoding, resampling, `loudnorm`, `rubberband` and the Vorbis encoder use floating point. The Windows and Linux
    wheels are separate builds, and may bundle different ffmpeg versions. So the bytes may differ between platforms,
    and a checkout on the other platform shows these Stages stale through `ffmpeg.version`. As with Blender
    (ADR 0010), the guard is the Owner's review of the game repo's diff. The Takes and their numbers are numpy over
    the decoded PCM, deterministic on one platform. Across platforms they may differ in the last bits, never by a
    sample of a cut on the fixtures.

## Consequences

- **Tests.** The CLI seam checks what a sound is: the Takes' times (±5 ms on the five-click fixture), the channels, the
  rate, the length, and the peak or loudness within 0.1 dB of the target. It checks that two builds give the same bytes.
  No test compares OGG bytes with a committed file, since the bytes depend on the platform's wheel. The sound Ops get
  golden tests on arrays and numbers, and the contact sheet is a PNG golden.
- **The glossary grows.** Sound, Take, Use, Variation and Provenance are new. Variant, Source, Op, Kind and Manifest are
  widened to cover recordings.
- **Spec principles.** Principle 9 adds audio files to LFS. Principles 2 and 11 name ffmpeg beside Blender as
  deterministic work that rebuilds. Principle 6 (the palette, binary Masks) doesn't apply to a sound.
- **A looped sound is not a Loop.** A Loop belongs to a room. A sound's `loop` is a flag, like a clip's, and the
  finding is `process.loop_seam`, not `loop.seam`.
- **LFS in a sound Project.** `init` adds `*.wav`, `*.flac`, `*.mp3` and `*.ogg` to the Project's LFS rules.
  `manifest install` writes the `kiripix-ours` rule for `*.ogg` into `<folder>/.gitattributes`, since a
  `.gitattributes` under the root can't match files outside it.
- **Still open, for later:** Takes from several recordings in one sound, and a picked set played at a set interval as a
  Check (0398 plays it; nothing measures it).
- The work tickets are 0395 (`import`, `source`, `slice`, `keep`, the ffmpeg helper and the lock), 0396 (the contact
  sheet), 0397 (`process`), 0400 (`export`, the Manifest's `sound` block), 0398 (UI) and 0399 (the generation trial).
