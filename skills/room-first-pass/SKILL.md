---
name: room-first-pass
description: Take a Kiripix room from its brief to export through the CLI, the first pass before the Owner's UI pass. Use when asked to do a room's first pass, build a room, or take a room to export.
---

# A room's first pass

You take one room from its brief to `kiripix export` through the CLI, then hand it to the Owner, who finishes it in the UI.
The goal is the Owner's minutes afterwards (`kiripix stats`): every Mask, Layer and Marker you place right is one they don't
place. On the laneway (ticket 0134) the Owner spent 19 minutes after a first pass that this skill writes down.

Learn the Commands from Kiripix itself: `kiripix --help`, `kiripix <command> --help`, `kiripix describe room` (every Stage's
parameters, Decisions and Checks) and `kiripix schema`. Every result has `findings`; each finding carries a `fix` (a command
you run) or an `owner_action` (only the Owner can do it). Run Commands with `--json` and read the findings, not the prose.

## The loop at every step

1. `kiripix next <room>` names the next Stage and the command to run, or what only the Owner can do.
2. Record the Stage's Decisions in one batch: write a JSON array to a file in `.kiripix/` and run
   `kiripix decide <room> <stage> --file <file> --json`. One file per Stage keeps the journal readable and the undo cheap.
3. `kiripix run <room> --json`, then `kiripix check <room> --json` (every built Stage's Checks).
4. Judge without looking at pixels where a Probe answers: `probe segment-preview` before a click or box Decision,
   `probe layer-stats`, `probe reach`. `kiripix preview <room> --stage <stage>` writes a PNG when you must look
   (`--brighten 1.8` for a dark room; `--stage palette --overlay reachable` shows the ground the Body reaches, since
   `reach` has no image of its own).

A `click` or `box` Decision makes a Runner call: it needs `run --rerun`, and plain `run` answers `needs-input` ("Runner not
run yet").

A step is done when its Stage is `done` (or `needs-review`, below) and its Checks have no error you can fix.

## Steps, in order

1. **Brief.** `kiripix set <room> brief width=... height=... mood=...` from the room's design. Size in whole tiles, and at a
   whole downscale of the Source (`fit` takes whole scales only): pick the scale that brings the room nearest its designed
   size in tiles, then check it against the game's size table (a door opening, an adult's 52 px). Say the scale you chose
   in the hand-over: every Decision below is in target pixels, so a changed brief undoes them all.
2. **Extend**, only for a room larger than one screen. `kiripix extend <room> canvas --side <side>` writes the canvas; the
   Owner (or an image model, if the Project drives one) paints the piece; `extend add <png>` joins it, reporting the
   residual, gain and seam. A corner piece takes two sides (`--side east,south`, `--keep across,down`). Then `extend done`
   and `pick` the joined Variant. Judge a join by its numbers: a residual under about 0.3 px is a good one.
3. **Source.** `import` the image; a lone Variant you may `pick` yourself. Several Variants: the choice is the Owner's.
4. **Fit.** `kiripix set <room> fit mode=downscale` for a painted Source (the default `grid` mode is for pixel art already on
   a grid, and leaves a painting at full size: `fit.size_mismatch`). Choose `offset_x`/`offset_y` so the crop keeps what the
   room needs; `fit.size_mismatch` gone is done. If 1-2 px outlines break into dashes (an AI painting at scale 3), try
   `dark_share=0.33 separation=0.12`.
5. **Layers.** Lift every object the Body walks behind: cars, poles, lamps, sheds, signs, a bin standing out from a wall.
   An object hugging a wall the Body can only stand in front of (lockers, a cabinet, a bench) needs no Layer. Try a click
   and a box with `probe segment-preview` and keep the one whose `box` covers the whole object: a click often returns only
   part (half a van on the laneway; the bottom rows of a 16 px bin in the dungeon), so a box is the usual answer. Set
   `min_piece` to drop specks `probe layer-stats` reports. A Stage with Runner Decisions you made lands in `needs-review`:
   that is the Owner's `accept` (`owner.required` if you run it: ask the Owner to run it at their terminal or in the UI),
   and the Stages below it wait. Record the Masks and Place Decisions meanwhile, so one `run` finishes the room after it.
6. **Masks.** A `border` on `solid` first. Then `solid` for walls, fences, house fronts, stairs and anything the Body can't
   enter: `polygon` for straight-edged things, `box` or `click` for objects. Mask an object's footprint on the floor, not
   its whole picture: whatever rises above the floor (a bench's back, a cabinet's top, the end of a backrest) is walkable
   ground beside or behind it. Look at a zoomed `preview` of each object's edges before drawing its polygon; on the
   dungeon a bench's north end was masked 16 px too far and the Owner had to erase it. `pit` for hazards and drops. Leave walkable
   ground clear; a doubtful case (a puddle: `pit` or ground?) goes in your hand-over.
7. **Palette.** First `kiripix set <room> palette strength=0 orphan_size=0`: the Owner's rooms take no dither and no
   orphan removal (a painted room's dither and despeckling muddy it). `run`, then read `palette.mapping_error`, and propose
   colours whether or not it fires: `kiripix op palette-suggest --asset <room> --add 32 --min-distance 0.02`. The
   Owner wants more colours than the Check asks for (the dungeon: 0.025 gave 6 colours, too few; 0.02 gave 16). The
   proposal goes to the Owner: `palette-add` is owner-only. Carry on with the current palette meanwhile.
8. **Place.** Markers, one batch:
   - the Spawns and the Exits, each Exit with `target_room` and `target_exit` (a room that doesn't exist yet gives
     `exit.no_room`; name it and say so in the hand-over). An Exit stands on walkable ground just inside its doorway; the
     game keeps its trigger area in its own room data, relative to the Exit, so it needs no `area` here;
   - the battle area as an `area` with `cell` set to the battle grid and `walkable: true`, its edges on whole cells; then
     `kiripix area-settle <room> <area>` settles the cells half covered by `solid` or `pit` (`area.ambiguous_cells`);
   - interactables (gates, doors, the clues the room's design names) as Markers on the walkable ground in front of them;
   - a `light` at each lamp the painting shows, if the game lights actors (its colour from the lamp); the Owner tunes them;
   - one y-sort line per foreground Layer: `probe layer-stats` gives each line ready to record; or `above` for a Layer that is
     always above the Body.
9. **Reach.** `run` and fix what's yours: `reach.unreachable_marker` and `reach.unreachable_link` are errors (a Marker
   placed inside `solid`, or a Mask gap closing a path). `reach.unreachable_island` is a warning: a fenced yard behind a
   closed gate is unreachable on purpose; list it in the hand-over rather than opening it. Looks and Loops are the Owner's.
10. **Export.** `kiripix export <room> --dry-run --json` first: it lists what would be written and refused. Then
    `kiripix export <room> --json`. `exit.no_room` for placeholder Exits, `exit.not_paired` while a neighbour still points
    elsewhere, and `export.merge_driver_missing` are expected; anything else is a finding to fix or hand over.

## Where you stop

Stop when `next` answers with an `owner_action`, or exit code 3 (`needs-input`, `needs-review`). That is normally
`layers` in `needs-review`. Keep going on what the Owner's answer doesn't change. After the Owner says to carry on, run `next`
again: a Stage that reads `todo` after their Decisions is ready to run, not waiting on them.

**At every stop, write a hand-over note on the Stage that waits:** `kiripix note <room> <stage> "<text>"` (at most 2,000
characters): why you stopped, and what's left for the UI (doubtful Masks with their boxes, Layers not lifted, Exits to rooms
that don't exist yet). The Owner reads it in `kiripix queue` beside the stop, long after this session is gone; a note stays
live until the Stage gets a newer Decision or an `accept`.

## Batch mode: many rooms, one session each

A chapter is about 30 rooms; one session over all of them grows its context with every room. `batch.py`, beside this file,
runs one fresh `claude -p` session per room, **in sequence** (the Runners share the GPU), and writes a report to
`.kiripix/first-passes/<date>.md`: per room, where it stopped, its notes, its Decisions per Stage in this pass and its tokens
(from each session's own usage), then `kiripix queue --match <glob>` as the Owner's starting point. From the art Project:

```
python .claude/skills/room-first-pass/batch.py --match "room.ch01_dungeon_*" --dry-run   # which rooms run, which are skipped
python .claude/skills/room-first-pass/batch.py --match "room.ch01_dungeon_*"
python .claude/skills/room-first-pass/batch.py room.ch01_dungeon_r01 room.ch01_dungeon_r02
```

A room with no Source is skipped with a line in the report, never guessed. `--timeout` (minutes, default 60) stops a session
that runs away; `--allowed-tools` lists what each session may run without asking (Kiripix, and reading and writing files).

When you are one of those sessions (the prompt says **batch mode**), nobody reads the conversation: never ask and never wait.
At a stop, record every Decision you still can, write the note, and end. If you can't find the room's size and mood (no brief
set and no design to read), write a note on `brief` saying what's missing and end: the report lists the room as skipped.

A Command the workflow needs that Kiripix lacks: say so in the hand-over, for a ticket. Work only through Commands; a
script that writes the Project's files by hand breaks the journal.

## The hand-over

End with a short note to the Owner:

- the room's status (`kiripix status`) and what waits on them: the `accept`, a Source to pick, a palette proposal's path;
- what's left for the UI: doubtful Masks (named, with their boxes), the Layers you didn't lift, unreachable ground left on
  purpose, Exits to rooms that don't exist yet;
- your Decision count per Stage, so their `kiripix stats <room>` afterwards measures the UI pass alone.
