---
status: done
milestone: M6
agent: reviewer
type: adr
parent: 0393-m6-sound-kind.md
---

# M6: ADR: a `sound` Kind and its Recipe

## The question

Kiripix's Kinds are images (room, prop, icon, character, sprite). Does a `sound` Kind fit the Stage graph, the
Manifest and export unchanged, or does it need its own path? Decide before 0395 builds anything.

## To decide (with the Owner where marked)

- **Recipe:** proposed `source → slice → pick → process → export`. `source` holds the recording (a raw download never
  goes to the game); `slice` finds Takes; `pick` is a Decision naming the Takes kept and their variation numbers;
  `process` applies trim, fades, speed, pitch, loop and loudness; `export` writes OGGs and the Manifest entry.
- **Sub-kinds:** `sfx`, `ui`, `ambience`, `music` as a field on the Asset (they differ in target loudness, channels and
  looping), not separate Kinds.
- **Settings:** the loudness and format table as Project settings in `kiripix.toml`, seeded from the game's `audio`
  skill.
- **Provenance and licence:** the source's URL, author and licence recorded at `source` and carried into the Manifest
  entry. Kiripix never writes credits: the game writes its own `CREDITS.md` line from the Manifest (Owner,
  2026-11-26).
- **Determinism:** the same inputs give the same OGG bytes (pinned ffmpeg version and encoder settings among the
  Stage's inputs); otherwise state what is deterministic.
- **IDs:** `sfx.footstep.asphalt` style IDs, the same as the game's `audio.json` (Owner: should export write
  `audio.json` entries, or only files and the game keeps the mapping?).

## Result

Drafted 2026-11-27: [docs/adr/0016-a-sound-is-a-kind-cut-into-takes-with-a-pinned-ffmpeg.md](../../docs/adr/0016-a-sound-is-a-kind-cut-into-takes-with-a-pinned-ffmpeg.md),
status proposed. The Owner's decisions of 2026-11-26 and 2026-11-27 are recorded in it as decided: export writes only the
OGGs and the Manifest entry (no `audio.json`, no `CREDITS.md`); ffmpeg from `imageio-ffmpeg==0.8.1` in `uv.lock`; 0397
split into 0397 (process) and 0400 (export); the game skill's table as Project settings.

- **Recipe:** source → slice → **keep** → process → export. `pick` is renamed `keep`, because a Pick (glossary) is the
  Decision choosing the Source, which a sound also has, with `kiripix pick` as its Command. An agent may record `keep`.
- **Use and IDs:** `use` (`sfx|ui|ambience|music`) and `sound_id` (`sfx.footstep.asphalt`) are Asset parameters. The
  Asset ID stays `sound.<name>`. Files are `<[sound] folder>/<use>/<sound_id less its prefix, dots as _>[_<n>].ogg` (numbered only when
  there are several, Owner 2026-11-27), with `[sound] folder = "res://audio"`: outside `[export.godot] root`, one stated exception.
- **Takes** are identified by `start_ms`/`end_ms`. They match on replay within 15 ms of the start and half the span. A
  moved bound is `needs-review`; a missing or split Take is `needs-input` (`keep.take_missing`, `keep.take_split`).
- **ffmpeg** lives only in `kiripix/recipes/ffmpeg.py` (like `blender_launcher.py`). Its version is a computed Stage
  input (`ffmpeg.version`). It rebuilds as Blender does (ADR 0010). Analysis is Ops over the decoded PCM.
- **Settings:** `[sound]` (`folder`, `rate`, `quality`) and `[sound.use.<use>]` (`prefix`, `channels`, `peak`, or `lufs`,
  `true_peak` and `lra`). `kiripix.toml` gets the next `schema_version` with a migration that adds nothing.
- **Provenance** is recorded per imported file in `imported.jsonl` (`--url`, `--author`, `--licence`). It's carried by
  `export` into a new optional `sound` block of the Manifest (schema 5). A missing author or licence is
  `sound.provenance_missing` (`owner_action`).
- **Determinism:** the same OGG bytes on the same platform with the locked wheel and fixed encoder flags
  (`-fflags +bitexact -flags:a +bitexact -map_metadata -1 -threads 1`). The bytes aren't promised across Windows and
  Linux.

The spec (§1, §2, §3, §4, §5, §6.8, §7, §9, §12, §14) and GLOSSARY.md edits are handed to the main session to apply.

Things the ADR changes in the work tickets:
- **0395:** the Decision is `keep`, not `pick`: `decide <id> keep` with `takes` as spans; `--takes 3,5,8,11` may stay as
  a convenience that writes spans. It adds `imageio-ffmpeg==0.8.1` to `pyproject.toml` and `uv.lock`, the ffmpeg
  helper, the `[sound]` settings and their migration, and the LFS lines for audio. It must check on Linux (CI) that the
  wheel there has libvorbis, `loudnorm`, `afftdn` and `rubberband`. Its findings gain `keep.take_missing`,
  `keep.take_split`, `sound.id_prefix` and `settings.sound_target`.
- **0397:** `loop.seam` becomes `process.loop_seam` (a Loop is a room's). Per-Take overrides are `process` Decisions
  naming a Take by its span. It writes `<n>.wav` and `process.json`. "Same inputs, same bytes" means on one platform.
- **0400:** the path is `<[sound] folder>/<use>/<name>_<n>.ogg`, not `<id>_<n>`. It adds the Manifest's `sound` block
  (schema 5, with its migration and the merge driver), `sound.provenance_missing` and `sound.name_taken`, and the
  `kiripix-ours` rule for `*.ogg` in the sound folder.
- **0396:** reads `process`'s `<n>.wav`. The Ops for waveform and spectrogram images are pure numpy.
