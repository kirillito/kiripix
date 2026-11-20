---
status: done
milestone: M5
agent: character-pipeline
type: ticket
---

# M5: held things, what the 2026-11-18 review found in `render` and `finish`

Left by the batch review of [0302](0302-m5-render-attached-things.md) and [0305](0305-m5-held-thing-colours.md).
The core half is [0312](0312-m5-held-things-review-core.md).

## What to fix

1. **A socket point lost to a same-named point.** `_socket_points` (`kiripix/recipes/render.py`) skips a socket when a given
   point already has its name but targets another bone (`points=grip_r=hand_r` with a clip attached at `grip_r`), so the
   socket gets no point, against 0302's promise. Name the socket's point so it never collides (the renamed `socket_<name>`
   checked against `POINT_NAME`), or refuse the clash with a finding. Fix the docstring, which says `grip_r@grip_r`.
2. **`line_skip` and a shared material name.** `character_finish.py` keeps only the first index per material name
   (`by_name = {n: i[0] ...}`), so `line_skip=Metal` skips the Model's `Metal` but not a held thing's. Skip every index of the
   name, as `palette` does.
3. **Every clip re-renders when any thing changes.** Each clip's render key holds every thing's current Variant. Key a clip on
   the things it holds and those numbered before them (a thing added later moves no earlier number), so adding `rake`
   re-renders only the clips that hold it.
4. **Dead branch.** `_check_attach` in `kiripix/recipes/clips.py` re-runs `attach_problem` (`clips.thing_twice`), which
   `decide` already refuses for every Decision. Drop the branch and the unreachable Check code, or say why it stays.

Stage `version` bumps where outputs change (1, 2).

## Acceptance criteria

- [x] CLI seam: a given point named like a socket still gets the socket's point; `line_skip` on a name the Model and a thing
      share skips both; importing a thing no clip holds re-renders no clip.
- [x] `uv run lint-imports` and `uv run mypy` pass.

## Result

Built, all four items:

1. A socket's point: `_socket_points` (`kiripix/recipes/render.py`) now gives the socket `socket_<name>` (then `_2`, `_3`...) when a
   given point already has its name on another bone; a given point on the socket's bone is still its point. The docstring says
   `rightforearm`, not `grip_r@grip_r`.
2. `line_skip`: `character_finish.py` skips every index of a material name (the Model's and a held thing's), a pair `a+b` as every
   combination, and the eye materials the same way.
3. A clip's render key holds the things it holds and those numbered before them (`own["things"]`), not every thing. A thing
   numbered after the last one any clip holds is no longer passed to Blender or listed in `render.json`'s `things` (it moves no
   number), so importing a thing no clip holds re-renders no clip (the Stage is stale and re-runs, drawing nothing); a clip newly
   holding a later thing re-renders only the clips that hold it.
4. `_check_attach` (`kiripix/recipes/clips.py`) no longer re-runs `attach_problem`; the Check code `clips.thing_twice` is gone
   (`decide` refuses it as `decision.invalid`, tested in `test_clip_attach.py`). The Check list in `test_character_clips.py` lost it.

Stage version bumps: `render` 3 to 4 (item 1 changes a point's name; item 3 changes every clip's key, so every clip with a hold
draws again once), `finish` 3 to 4 (item 2).

Tests: `tests/cli/test_held_things_review_render.py` (3 tests); `test_render_held.py`'s "thing added" test now expects no
re-render.

### Review follow-up (2026-11-18)

- The Wearable's `finish` runs the character's finish code, so the `line_skip` change reaches it too: its `version` is bumped 4
  to 5.
- **`clips.thing_twice` removed, on purpose.** Its condition is refused by `decide` for every Decision (`decision.invalid`), so
  the Check could only fire on a hand-edited journal. A finding code is retired, not renamed.
- **Accepted:** a thing laid by hand (no `imported.jsonl` line) is numbered after the imported ones, by ID, so a hand-laid thing
  whose ID sorts first can move a later hand-laid thing's number and re-render the clips that hold it. Things imported through
  `import` never move. No mtime rule comes back (0312 removed it).
