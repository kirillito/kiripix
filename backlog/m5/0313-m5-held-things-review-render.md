---
status: todo
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

- [ ] CLI seam: a given point named like a socket still gets the socket's point; `line_skip` on a name the Model and a thing
      share skips both; importing a thing no clip holds re-renders no clip.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
