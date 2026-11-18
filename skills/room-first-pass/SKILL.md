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
   `probe layer-stats`, `probe reach`. `kiripix preview <room> <stage>` writes a PNG when you must look.

A step is done when its Stage is `done` (or `needs-review`, below) and its Checks have no error you can fix.

## Steps, in order

1. **Brief.** `kiripix set <room> brief width=... height=... mood=...` from the room's design. Size in whole tiles.
2. **Extend**, only for a room larger than one screen. `kiripix extend <room> canvas --side <side>` writes the canvas; the
   Owner (or an image model, if the Project drives one) paints the piece; `extend add <png>` joins it, reporting the
   residual, gain and seam. A corner piece takes two sides (`--side east,south`, `--keep across,down`). Then `extend done`
   and `pick` the joined Variant. Judge a join by its numbers: a residual under about 0.3 px is a good one.
3. **Source.** `import` the image; a lone Variant you may `pick` yourself. Several Variants: the choice is the Owner's.
4. **Fit.** `kiripix set <room> fit mode=downscale` for a painted Source (the default `grid` mode is for pixel art already on
   a grid, and leaves a painting at full size: `fit.size_mismatch`). Choose `offset_x`/`offset_y` so the crop keeps what the
   room needs; `fit.size_mismatch` gone is done.
5. **Layers.** Lift every object the Body walks behind: cars, poles, lamps, sheds, signs. Use a `box` Decision for anything
   bigger than about 40 target px: a single click returns only part of a large object (half a van, a car's roof). Click the
   small ones. Set `min_piece` to drop specks `probe layer-stats` reports. A Stage with Runner Decisions you made lands in
   `needs-review`: that is the Owner's `accept`, and the Stages below it wait.
6. **Masks.** A `border` on `solid` first. Then `solid` for walls, fences, house fronts, stairs and anything the Body can't
   enter: `polygon` for straight-edged things, `box` or `click` for objects. `pit` for hazards and drops. Leave walkable
   ground clear; a doubtful case (a puddle: `pit` or ground?) goes in your hand-over.
7. **Palette.** `run`, then read `palette.mapping_error`. Above the Project's target (0.015 on the Owner's game), propose
   colours: `kiripix op palette-suggest <fit.png> --min-distance 0.025` (0.03 adds too few, 0.02 adds near-duplicates). The
   proposal goes to the Owner: `palette-add` is owner-only. Carry on with the current palette meanwhile.
8. **Place.** Markers, one batch:
   - the Spawns and the Exits, each Exit with `target_room` and `target_exit` (a room that doesn't exist yet gives
     `exit.no_room`; name it and say so in the hand-over);
     an Exit's trigger area as an `area` box at the room's edge;
   - the battle area as an `area` with `cell` set to the battle grid and `walkable: true`, its edges on whole cells; then
     `kiripix area-settle <room> <area>` settles the cells half covered by `solid` or `pit` (`area.ambiguous_cells`);
   - interactables (gates, doors) as Markers;
   - one y-sort line per foreground Layer: `probe layer-stats` gives each line ready to record; or `above` for a Layer that is
     always above the Body.
9. **Reach.** `run` and fix what's yours: `reach.unreachable_marker` and `reach.unreachable_link` are errors (a Marker
   placed inside `solid`, or a Mask gap closing a path). `reach.unreachable_island` is a warning: a fenced yard behind a
   closed gate is unreachable on purpose; list it in the hand-over rather than opening it. Looks and Loops are the Owner's.
10. **Export.** `kiripix export <room> --json`. `exit.no_room` for placeholder Exits and `export.merge_driver_missing` are
    expected; anything else is a finding to fix or hand over.

## Where you stop

Stop when `next` answers with an `owner_action`, or exit code 3 (`needs-input`, `needs-review`). That is normally
`layers` in `needs-review`. Keep going on what the Owner's answer doesn't change. After the Owner says to carry on, run `next`
again: a Stage that reads `todo` after their Decisions is ready to run, not waiting on them.

A Command the workflow needs that Kiripix lacks: say so in the hand-over, for a ticket. Work only through Commands; a
script that writes the Project's files by hand breaks the journal.

## The hand-over

End with a short note to the Owner:

- the room's status (`kiripix status`) and what waits on them: the `accept`, a Source to pick, a palette proposal's path;
- what's left for the UI: doubtful Masks (named, with their boxes), the Layers you didn't lift, unreachable ground left on
  purpose, Exits to rooms that don't exist yet;
- your Decision count per Stage, so their `kiripix stats <room>` afterwards measures the UI pass alone.
