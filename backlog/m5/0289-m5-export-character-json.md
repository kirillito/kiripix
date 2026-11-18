---
status: done
milestone: M5
agent: none
type: ticket
---

# M5: a character's Godot export carries `character.json`

Spec §9 (Character). Asked for by the game (urban-mystery-club, its ticket 0085).

## The gap

The game needs two things Kiripix already builds for every character, in its `out/export/character.json`, but never writes
into the Godot project:

- the foot-contact frames, `clips[].events.foot` ([0172](../m4/0172-m4-foot-contact-frames.md)), for footstep sounds on
  `walk` and `run`;
- the per-frame named points, `clips[].directions.<dir>[].points.<name> = {x, y, hidden}`, pivot-relative (render's `points`,
  [0237](0237-m5-render-records-named-points.md)), so the game can draw a held phone at the hand.

`kiripix export` writes `color.png`, `normal.png`, `ramps.png`, `frames.tres`, `texture.tres` and `<id>.tscn` only. A room
already exports its data file (`room.json`, [0140](../m4/0140-m4-export-masks-and-room-json.md)); a character should too.

## What to build

- `kiripix export character.<id>` also writes `character.json` beside `<id>.tscn`, such as
  `res://art/kiripix/character/mc03_male/character.json`. The game's `CharacterLayer` reads `<scene dir>/character.json`.
- It is the built file, byte for byte: same `schema_version` and keys. Its `files` (`color.png`, `normal.png`) are bare names
  relative to the file, and both atlases sit beside it in the game too, so nothing in it needs rewriting, and it has no
  `res://` paths. A sprite is exported as a character, so a sprite's folder gets it as well.
- It is an exported file like the others: hashed in the Manifest's `files`, counted in written / unchanged, stale-checked
  (`next` names `export` when it differs), and removed with the character by `--prune`.
- Merge: `character.json` joins `OURS_PATTERNS` (its name only, not every `*.json`), so `manifest install` writes
  `character.json merge=kiripix-ours` to `<root>/.gitattributes`, export's driver probe checks it, and the warning names it. A
  clone installed before this warns until `kiripix manifest install` adds the one missing rule.
- README (what `kiripix export` writes for a character) and spec §9 (the Character row, and the merge rules).

## Acceptance criteria

- [x] CLI seam: a character's export writes `character.json`, equal to the built one, with its foot events and points; the
      Manifest lists it.
- [x] A second export with nothing changed writes nothing and leaves the counter.
- [x] `manifest install` writes the `character.json` rule, and a clone without it gets `export.merge_driver_missing`.
- [x] `uv run lint-imports` and `uv run mypy` pass.
- [x] The seven characters of the art Project re-exported; each game folder has `character.json` with `events.foot` on `walk`
      and `run` and `points.hand_r` / `points.hand_l` on the `phone_in`, `phone` and `phone_out` frames.

## Result

`_character_files` ([export/__init__.py](../../kiripix/export/__init__.py)) adds `<folder>/character.json`, the built file's
bytes, so the Manifest, written / unchanged, `next`'s stale check and `--prune` take it like the other files. Nothing is left
out: `files` holds `color.png` and `normal.png`, names relative to the file, and both are beside it in the game, so there is
no `res://` path to rewrite. A sprite's folder gets one too, since a sprite is exported as a character. No Stage writes
anything new, so no `version` bump and no rebuild; the first export after this writes `character.json` and the Manifest only.

`OURS_PATTERNS` ([export/merge.py](../../kiripix/export/merge.py)) adds `character.json`, so `manifest install` writes
`character.json merge=kiripix-ours`, the driver probe checks it, and `export.merge_driver_missing` names it. A clone installed
before this warns once; `kiripix manifest install` appends the one rule and keeps the rest. `kiripix describe character`
lists no exported files, so it is unchanged.

Tests: `test_character_json_reaches_the_game_byte_for_byte_and_follows_a_rebuild` (test_export_character),
`test_the_events_reach_the_game_in_its_character_json` (test_foot_events), `test_the_points_reach_the_game_in_its_character_json`
(test_character_points, which also checks a second export leaves it unchanged),
`test_install_covers_character_json_and_a_clone_installed_before_it_warns_until_installed_again` (test_manifest_merge); the
character's and sprite's expected file lists include it.

Art Project, 2026-11-17: `kiripix manifest install` added the rule to `game/art/kiripix/.gitattributes`; `kiripix export` of
`mc03_male`, `mc03_male_clothes01`, `mc03_male_clothes02`, `mc03_female`, `mc03_female_clothes01`, `mc03_female_clothes02` and
`sanjay` wrote each one's `character.json` (and Manifest), no rebuild. Each is schema_version 5, byte-equal to the built file;
`walk` and `run` have `events.foot` (male `walk` [3, 7], female [4, 7], `run` [4, 7]), and every frame of `phone_in` (104),
`phone` (216) and `phone_out` (136) has `points.hand_r` and `points.hand_l`.
