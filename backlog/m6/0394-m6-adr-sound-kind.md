---
status: todo
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

An ADR in `docs/adr/`, the spec's §5 (Kinds) and §14 (M6) updated, glossary terms (Take, ...).
