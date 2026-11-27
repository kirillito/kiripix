---
status: done
milestone: M6
agent: character-pipeline
type: ticket
depends_on: [0354-m6-provider-research-actors.md]
---

# M6: a PixelLab ZIP with states: each state is a clip

Found by [0354](0354-m6-provider-research-actors.md). PixelLab keeps a pose as a *state* of a character, and the group's ZIP
holds `Idle/rotations/south.png`, `hop/rotations/south.png`, `dazed/rotations/south.png` ... The naming rule
(`kiripix/recipes/sprite_names.py`) treats `rotations` as a container and places each as the clip `idle`. Then
`_Frames.join_rotations` (`kiripix/recipes/sprite_frames.py`) drops all but the first for a direction as if an animation had
given it, so nothing lands in `duplicates` and there is no finding. In 0354 five poses became one clip, and the one kept as
`idle` was `dazed`.

## What to build

- `<state>/rotations/<direction>.png` is the clip of the state's folder (`Idle` and a lone `rotations/` stay `idle`; a ZIP
  whose one character has one state reads as today).
- Two rotations for one clip and direction, with no animation there, are a `clips.duplicate_name` finding, not a silent drop.
- A way to leave states out when importing: the ZIP of any run holds every state of the group, rejected tries included
  (`hop`, `hop_2`). A `sheet` Decision may do already; say which in the Result.
- Bump `frames`' `version`.

## Acceptance criteria

- [x] A test ZIP with three states gives three clips; one with a lone `rotations/` gives `idle` as now.
- [x] Two states that map to one clip name give `clips.duplicate_name`.
- [x] 0354's raccoon ZIP (`0354-trial/runs/016-state_hurt2/export.zip`) imports with its poses as clips.

## Tests

CLI seam, `tests/cli/test_sprite.py`.

## Result

- The naming rule (`kiripix/recipes/sprite_names.py`) reads `<state>/rotations/<direction>.png` as a rotation of the clip
  named after the state's folder (`Placed.state`, `Placed.raw`): `dazed/rotations/south.png` is `dazed`, `Idle/rotations/...`
  is `idle` as before, and a lone `rotations/` is still `idle`. An animation's clip is its own folder, whatever state holds it.
  A clip's `raw` in `frames.json` is the state's folder (`Idle`, not `idle`); a rename by either spelling still matches.
- `_Frames.join_rotations` drops a rotation only where an animation gave that clip the direction. Two rotations for one clip
  and direction (`{"hop_2": "hop"}` beside `hop`, or `Hop` and `hop`) are `clips.duplicate_name`, one per direction.
- No Decision could leave states out (renaming `hop_2` onto `hop` collides), so the ZIP form of the `sheet` Decision takes
  `leave_out`: a list of folder names, animations or states, matched snake_case and before any rename, such as
  `{"file": "...", "clips": {"hop_2": "hop"}, "leave_out": ["hop"]}`. The Stage notes what it left out. The schema only gains
  an optional key, so no migration.
- `frames` `version` 1 → 2, so `frames` is stale on every sprite; only a ZIP with states builds anything different.
- 0354's raccoon ZIP (`0354-trial/runs/016-state_hurt2/export.zip`, 4 directions) gives `dazed`, `hop`, `hop_2`, `hurt`,
  `hurt_2`, `idle` (from `Idle`), `swipe`, `swipe_2` and `walking_on_all_fours`. With `clips {"hop_2": "hop", "hurt_2":
  "hurt"}` and `leave_out ["hop", "hurt", "swipe_2", "walking_on_all_fours"]` it gives `dazed`, `hop`, `hurt`, `idle`,
  `swipe` with no finding. Checked by hand in a scratch Project; the ZIP is not in git, so no test reads it.
- Tests (`tests/cli/test_sprite.py`): `test_each_state_of_a_pixellab_zip_is_a_clip`,
  `test_two_states_that_map_to_one_clip_are_a_duplicate_name`, `test_a_sheet_decision_leaves_states_out`; the lone
  `rotations/` case stays covered by `test_a_zip_in_pixellabs_layout_runs_to_the_sheet_with_no_decision` and
  `test_a_pixellab_zip_with_its_metadata_json_runs_with_no_warning`.
- Spec §6.4's `frames` row names the state rule and `leave_out`.
