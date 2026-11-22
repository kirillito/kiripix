---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0328-m6-district-probe.md]
---

# M6: a one-way Exit: `one_way` on an Exit Marker

Spec §6.1 (`place`, Exit pairing) and §9 (Room). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Follows
[0328](0328-m6-district-probe.md), whose `district` reserves the pairing `one_way` but never gives it: nothing in a Marker
says that no return is meant, so a drop through a pit or a door that locks behind the player reads `unpaired` and fails
`export --all`. The Owner asked for a Marker field on 2026-11-20.

## What to build

- **The field:** an Exit Marker (`marker` Decision on `place`, `type = exit`) takes `one_way` (boolean, default false).
  `target_room` and `target_exit` stay required: the target Exit is where the player arrives.
- **The pairing rule** (`export/checks.py` `_pairing`, the one rule `check`, `export` and `district` share): a `one_way`
  Exit needs its target room and target Exit to exist (`exit.no_room`, `exit.no_exit` as now), and nothing to point back,
  so it never gives `exit.not_paired`. `district` gives it `one_way` (or `outside` when the target is outside the district).
  An ordinary Exit that points at a `one_way` Exit is still checked as now.
- **What `place` writes:** `markers.json` writes `one_way` on every Exit, `false` when unset, so a reader needs no default
  (as the emitter's optional fields are). That is a format change: bump `markers.json`'s `schema_version`, with its
  migration, and `place`'s `version`. A parameter at its default isn't in the hash, but the written file changes, so every
  room's `place` rebuilds once.
- **Export:** `room.json`'s Exits carry `one_way`, a `schema_version` bump (to 14, or to 15 if
  [0342](0342-m6-export-room-normals.md) lands first: they take turns), with its migration, and the export Stage's
  `version` bump. The Godot scene is unchanged: the game decides what a one-way Exit does.
- **UI:** the place screen's Exit form gets a "One-way" checkbox; `district` view draws a `one_way` arrow with one head.
  Name the follow-up for `ui-engineer` in the Result if it isn't done here.

## Acceptance criteria

- [x] CLI seam: room A's Exit to room B's Exit, `one_way` true, with B's Exit pointing elsewhere: `check --all` has no
      `exit.not_paired`, and `district` gives `one_way`; without `one_way` it is `unpaired`, as now.
- [x] CLI seam: a `one_way` Exit to a missing room or Exit still gives `exit.no_room` or `exit.no_exit`.
- [x] `markers.json` and `room.json` carry `one_way` on every Exit; an old version is refused with its rebuild (the Owner's decision, below); the version bumps are named
      in the Result.
- [x] Spec §6.1 and §9 updated.

## Result

An Exit Marker takes `one_way` (boolean, default false); `target_room` and `target_exit` stay required.

- **Rule:** `export/checks.py` `_pairing` returns no finding for a `one_way` Exit whose target room and Exit exist
  (`exit.no_room`, `exit.no_exit` as before); `check`, `export` and `district` share it. `district` gives `one_way`, or
  `outside` for a target outside the district. An ordinary Exit pointing at a `one_way` Exit is checked as before.
- **Version bumps:** `markers.json` `schema_version` 3 to 4 (every Exit has `one_way`, `false` when unset); `place` `version`
  3 to 4; `room.json` `schema_version` 13 to 14 (Exit Markers carry `one_way`); `export` Stage `version` 4 to 5. Every room's
  `place` and `export` rebuild once. Ticket 0342 now takes `room.json` 15 and `export` 6 (its text is updated).
- **Migration:** both files are Stage outputs: an old one is refused naming the rebuild (`stage.output_unreadable`,
  `export.room_invalid`), as for every earlier bump, and the version bump makes the Stage stale so the rebuild is one run.
- The Godot scene is unchanged. Spec §6.1 and §9 updated. Tests: `tests/cli/test_one_way_exit.py`; existing tests moved to
  the new versions.
- **UI follow-up for `ui-engineer` (not done here, `web/` untouched):** the place screen's Exit form gets a "One-way"
  checkbox (writes `one_way` in the `marker` Decision); the district view draws a `one_way` pairing as an arrow with one head.

**The Owner's decision, 2026-11-20:** no migration function for this bump. An old file is a Stage's rebuilt output, so it is refused with a finding that names the rebuild (CLAUDE.md's rule for rebuilt output), and the `version` bump makes the Stage stale, so one `run` rebuilds it. That stands in for "with its migration" above.
