---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: a Project clip table, so every body plays the same timing

Spec §4 (`kiripix.toml`), §6.3 (clips) and §16 (open decision 9). Part of [0236](0236-m5-the-games-next-needs.md), item 4. The
game's `docs/backlog/m3/0072-m03-clips-and-directions.md`.

## The gap

The game plays one timing on any body: `idle`, `walk`, `run` and `phone`, with the same frame count, fps and loop on all
four MC variants and Sanjay. Today they differ. `idle` was 8 frames at 4 fps on one body and 45 at 12 on another, until the
gate cut `mc03_female`'s by hand.

Bases ([0165](../m4/0165-m4-characters-share-a-base.md)) share clip Decisions only between a base and the characters made
from it. The MC's two bodies are two bases, with two skeletons and two sets of clip Decisions, so bases don't cover this.

The ramp table ([0167](../m4/0167-m4-project-ramp-table.md)) solved the same problem for Ramps: a Project list that every
character must match, and a Project check.

## What to build

- **`[[character.clips]]` in `kiripix.toml`** (bump `schema_version`, with its migration; it must keep the Owner's comments,
  [0235](0235-m5-settings-writes-keep-comments.md)): each row has a clip name, `frames` (the rendered frame count),
  `fps`, `loop`, and optionally `foot` (the clip must have foot frames, 0172).
- **A Command that fills it** from one character's decided clips, beside `ramps-add`, naming the clips to take. Without it the
  Owner writes the rows by hand. Pick the name to match `ramps-add`.
- **A Project check, `clips.timing_differs`**: on each character that has a clip named in the table, the built clip's
  frame count, fps and loop must match the row, and foot frames must exist when `foot` is set. The finding names the
  character, the clip and what differs. Its `fix` is the clip Decision that brings it in line, when one can (a `still` or a
  range changes the frame count, so say when only the Owner can choose: `owner_action`). A character without that clip
  raises nothing, because NPCs needn't have `phone`.
- `check --all` and `export --all` run it, as `palette.parts_differ` runs.
- `sprite` Assets are checked too, when their clip has the table's name. A one-frame PixelLab idle will differ, so it's a
  warning there, not an error. Say so in the finding.

## Acceptance criteria

- [x] CLI seam: two characters, one matching the table and one with `idle` at another fps, give one
      `clips.timing_differs` naming the second. A character lacking a table clip raises nothing.
- [x] The fill Command writes rows from a character, and refuses a clip the character hasn't decided.
- [x] A commented `kiripix.toml` keeps its comments through the migration (once 0235 has landed).
- [x] Contract samples for the new Command. Spec §4 and §6.3 describe the table. The glossary gets **Clip table** next to
      **Ramp table**.

## Result

- `[[character.clips]]` (`ClipSpec`: `name`, `frames`, `fps`, `loop`, `foot`) in `kiripix.toml`; Project `schema_version` 7, with the
  pure migration `_add_clip_table` (an empty list); the template carries a commented example. A name twice fails to load
  (`clips.name_twice`).
- `clips-add <character> --clips a,b [--foot a] [--dry-run]`, agent-runnable (the Owner's choice, 2026-11-17: the table makes nothing stale, and a differing row is refused, never changed), `kiripix/commands/clips_add.py`. It takes frames, fps and
  loop from the character's built `clips.json`; refuses a clip the character hasn't decided (`clips.not_decided`), one not built
  (`clips.not_built`), `--foot` on a clip without foot frames (`clips.no_foot_frames`) and a row that differs
  (`clips.row_differs`). Written with `save_settings`, so comments stay.
- Project check `clips.timing_differs` in `kiripix/core/cliptable.py`, run by `check --all` and, with errors refusing and warnings
  passing, by `export --all` (it checks the table before anything is planned). A character's finding is an error; its `fix` is
  the `clip` Decision with the table's fps and loop, and it is an `owner_action` when only a range, `speed` or `still` can fix the
  frame count, or the clip has no foot frames. A sprite's finding is a warning that says so, read from `fit`'s `render.json`, with
  a `decide <sprite> frames` fix for fps and loop. A foot row is not asked of a sprite (it has no foot events).
- `describe project` shows the table (`clips`, `clips_example`). Spec §4, §6.3, the CLI list and the glossary (**Clip table**).
- Tests: `tests/cli/test_clip_table.py`; contract sample for `clips-add`.

