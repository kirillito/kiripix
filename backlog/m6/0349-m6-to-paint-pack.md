---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0348-m6-brief-renders-the-prompt.md, 0327-m6-match-scope.md]
---

# M6: `kiripix to-paint`: every prompt and canvas a district needs, in one folder

Spec §10.5 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). The name `to-paint` is a placeholder;
the Owner may rename it.

## The gap

To paint a district's Sources, the Owner visits each room for its prompt, and for a multi-screen room runs
`extend <id> canvas` for each side. With 30 rooms, that's the session work the Owner does before any first pass can start.

## What to build

A Command that records nothing: `kiripix to-paint --match <glob> [--out <folder>]` (default
`.kiripix/to-paint/<date>/`). For every matched room waiting on its Source, it writes:

- **A room with no picked Source and no `extend` in progress:** `<nn>-<room>.prompt.txt` (the brief's prompt from
  [0348](0348-m6-brief-renders-the-prompt.md)).
- **A room with an `extend` in progress:** its next canvas, as `extend <id> canvas` would write it for the side the brief's
  size still needs (`<nn>-<room>.<side>.png`), with its prompt.
- **`index.md`:** one line per room in the order to paint, saying what to make and **what to name the file that comes back**
  (`<room>.png`, `<room>.<side>.png`), so [0350](0350-m6-source-inbox.md)'s inbox files it.
- A room with no brief is listed under "no brief yet", with the command to write one. A room whose Source is picked isn't
  listed.

## Acceptance criteria

- [ ] CLI seam: a district of three test rooms (one with no Source, one mid-`extend`, one done) gives one prompt, one canvas
      and an index with two entries and their return names.
- [ ] CLI seam: nothing in the Project changes (input hashes and journals as before).
- [ ] `to-paint` has a sample in `tests/cli/test_contract.py`; spec §10.5 lists it.

## Result

`kiripix to-paint --match <glob> [--out <folder>]` (`kiripix/commands/to_paint.py`, a Probe, exposed over MCP). No Stage
`version` bump: no Stage output changed.

- **The names are in one place:** `kiripix/core/paint.py` (`return_name`, `prompt_name`, `canvas_name`, and
  `parse_return_name` for `inbox` to import: `alley.png` is ("alley", []), `alley.east.png` is ("alley", ["east"])). The Asset's
  name without its Kind prefix, so `<room>.png` and `<room>.<side>.png`.
- **The canvas code is reused:** `extend.plan_canvas` (new, the part of `write_canvas` that makes the canvas) and
  `extend.next_side`; `write_canvas` now calls the first.
- **Waiting on its Source** is: no picked Source, or live `extend` pieces. A room with a picked Source and no pieces isn't listed.
- **The side** a mid-`extend` room needs: east while the joined image is narrower than the brief, then south. The size to
  reach is the brief's width and height, times the fit's `scale` when it is in `grid` mode and set (otherwise 1: the Source's own
  scale isn't known before `fit`). One side at a time, so no corner canvas. A joined image already big enough is listed as
  `done` with no files (`kiripix extend <id> done`).
- **The prompt** is the brief's built `prompt.txt`, never rendered here. A brief that isn't `done` (not built, stale or failed)
  is listed under "no brief yet" with `kiripix run <id> brief` (finding `to_paint.no_brief`, info, `fix`); a built brief with no
  `prompt.txt` (the Project has no room template) is `to_paint.no_prompt` (info, `owner_action`). A mid-`extend` room with
  either gets no files.
- **Records nothing:** the canvas isn't written to the Asset's `extend/canvas.png`, and `canvas.json` isn't written. `inbox`
  (0350), filing `<room>.<side>.png`, must write the canvas record itself (`extend.write_canvas` with the same side and
  default keep, deterministic from the current image) before `extend add`.
- A matched Asset that isn't a room: `to_paint.not_a_room` (info). With nothing to write, no folder is made.
- Tests: `tests/cli/test_to_paint.py`; sample in `tests/cli/test_contract.py`; REST body in `tests/cli/test_serve.py`; spec §10.5.


**Review fixes (2026-11-20):** `paint.parse_return_name` was unused (`inbox.parse` reads the names) and is gone. `to-paint` exits with the worst error of a room it couldn't read (it exited 0). `plan_canvas` returns a `PlannedCanvas` NamedTuple. The "not a room" finding's `fix` is `kiripix status --kind room`.
