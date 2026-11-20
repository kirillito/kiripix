---
status: done
milestone: M5
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: Claude's first pass on a room, written down as a repeatable workflow

Spec §1 (goal 2, "faster") and §14 (M2's first-pass trial). Part of [0236](0236-m5-the-games-next-needs.md), cross-cutting.
Done in the main session (doc work; no agent).

## The gap

On the laneway ([0134](../m4/0134-m4-trial-room-extended-both-ways.md)), Claude's first pass through the CLI took the room
from its joined Source to export with Layers, Masks, Markers and an area. The Owner judged it very good, then spent 19
minutes in the UI. The first pass lives only in transcripts. Each new session works it out again, at a cost in tokens, and
it may do it differently.

A chapter is about 30 rooms. A first pass that runs the same way every time is the cheapest cut in the Owner's time per room
before M6's `gen`.

## What to build

- **A skill** (a `SKILL.md`, per the `writing-for-agents` guidance) for a Claude session in the art Project. Kiripix ships it,
  and the art Project installs it. It covers the steps, in order:
  - the brief and `extend` canvases;
  - `fit` and its crop;
  - Layers by `box` for anything bigger than about 40 target px (0134);
  - `solid` and `pit`, with `border`;
  - the palette, with `palette-suggest --min-distance 0.025` when a new kind of room needs colours (0134);
  - Spawns, Exits and their trigger areas, and a battle area on whole cells;
  - `reach` and the walk-test findings to fix;
  - export.

  It also says where the session stops for the Owner, and what to hand over: what's left for the UI, and the `stats`
  command.
- The workflow names Commands and findings, never internals. It uses only `--help`, `describe`, `next` and `check`, as the
  acceptance test's agent does.
- Where the workflow needs a Command Kiripix lacks, file a ticket instead of scripting around it.

## Acceptance criteria

- [x] The skill is in the repo, with a line in the README on installing it in a Project.
- [x] A fresh session with the skill takes the next ch01 room (not `harbor_front`) through its first pass. Its tokens and
      the Owner's UI minutes afterwards (`stats`) are recorded here, against the laneway's 19 minutes.

## Result (2026-11-17)

- **The skill:** [skills/room-first-pass/SKILL.md](../../skills/room-first-pass/SKILL.md), model-invoked (a session asked
  for a room's first pass reaches it). It is the laneway's first pass (0134) as ten steps (brief, extend, source, fit, Layers,
  Masks, palette, place, reach, export), each ending on its Stage `done` with no fixable error, plus the loop at every step
  (`next`, one `decide --file` batch per Stage, `run`, `check`, Probes before looking), where the session stops (an
  `owner_action` or exit code 3, normally `layers` in `needs-review`; and `todo` after the Owner's Decisions is ready to run,
  as 0233 found), and the hand-over (what waits on the Owner, what's left for the UI, the Decision count for `stats`).
  It names only Commands and finding codes, and points at `--help`, `describe room` and `schema` for the rest.
- **README:** a line under "Further reading" on copying the folder to `.claude/skills/` in an asset Project.
- **No new Command found missing** while writing it: `area-settle` (0279), `palette-suggest` (0280) and `probe layer-stats`
  cover what 0134 scripted by hand.
- **Left (the Owner):** the real run on the next ch01 room, its tokens and the Owner's `stats` minutes afterwards, against
  the laneway's 19. The ticket stays `todo` until then.

## The run (2026-11-19)

No painted Source exists for a new ch01 room, so the Owner chose to redo a dungeon room from scratch:
`room.ch01_dungeon_r02_pass`, from `ch01-dungeon-r02.jpeg` (R2, the staff vestibule, in the game's
`docs/maps/ch1-dungeon-lower-bay-station.md`). The session didn't read the old r02's Decisions.

- **Brief:** 288×224 (18 × 14 tiles), `fit` downscale at scale 4, `offset_x=24`. The map gives R2 16 × 12 tiles; at
  scale 4 the lockers are about 45 px against the 52 px adult. The old r02 was 560×416 (scale 2: doorways about 100 px).
  The Owner should confirm the scale before the UI pass, since a new brief undoes every Decision.
- **Layers:** `bin` and `extinguisher`, both by `box`: a click returned only part of each, even at 16 px. Lockers, cabinet
  and bench hug walls the Body only stands in front of, so they aren't lifted. One piece each, no specks.
- **Stop:** `layers` in `needs-review`. The session's `accept` is refused (`owner.required`), as it should be; the Masks
  and Place Decisions were recorded meanwhile, and one `run --rerun` after the Owner's accept built the room to export.
- **Masks:** a `border` and 7 `solid` polygons. **Place:** `spawn.main`, `exit.north` (to r01's `exit.south`),
  `exit.south` (to r03's `exit.north`), `battle.vestibule` (7 × 3 cells of 32 px, no ambiguous cells),
  `interact.noticeboard`, `interact.lockers`, two lights at the fluorescent tubes, two y-sort lines.
- **Reach:** every Marker and the battle area reached, no islands, no gaps.
- **Palette:** `palette.mapping_error` 0.0176; `palette-suggest --asset … --add 16 --min-distance 0.025` proposes 6
  colours (0.0154 → 0.0143 by its own measure), at
  `.kiripix/palette-proposals/room.ch01_dungeon_r02_pass-75af346b/`. Adding them is the Owner's.
- **Export:** 7 files and the Manifest under `res://art/kiripix/room/ch01_dungeon_r02_pass/`, overwriting nothing.
  Findings: only `exit.not_paired` ×2, because r01 and r03 still point to the old r02.
- **Decisions:** source 1, layers 2, masks 8, place 10 (21; `stats` total 0.0 Owner minutes before the UI pass).
- **The skill, corrected from the run:** `preview --stage` (not a positional Stage) and `--overlay reachable` on
  `palette`; `run --rerun` for Runner Decisions; a box even for small objects when a click is partial; walls-hugging
  objects need no Layer; the Owner runs `accept`; record Masks and Place while it waits; the brief's whole scale; Exit
  trigger areas live in the game's room data (the laneway placed none either); `palette-suggest --asset`; lights;
  `export --dry-run` first.
- **Found on the way, not filed:** `check` reports r01's `exit.south` leading to r01's own `exit.north`, and r03's
  `exit.north` to r03's own `exit.south`. The old dungeon rooms' Exits point into themselves.
- **No new Command found missing.**
- **The Owner's review of the run:** *major*: the palette needs `strength=0` and `orphan_size=0`, and more colours. The
  room now has both settings, and `palette.mapping_error` no longer fires. A new proposal at `--min-distance 0.02` gives
  16 colours (0.0154 → 0.0094) at `.kiripix/palette-proposals/room.ch01_dungeon_r02_pass-47af78a2/`. *Minor*: the
  bench's `solid` reached 16 px past its seat at the north end (y 113–128). It's now erased by one polygon Decision, with
  reach unchanged, and the room is re-exported. The skill now sets both palette parameters first, proposes at 0.02, and
  masks an object's footprint only.

**The Owner's UI pass (`stats`, 2026-11-19):** 2.95 minutes in the UI and no UI Decisions, against the laneway's 19.23
minutes and 94 Decisions. By Stage: palette 1.27, layers 0.62, brief 0.38, place and loops 0.17 each, export 0.15,
looks 0.13, masks and reach 0.03 each. The two review findings above went back to the session rather than into the UI,
so the fixes' own time isn't in the 2.95. The Owner's earlier pass on the old `room.ch01_dungeon_r02` has 46 Decisions
and no tracked minutes, so it gives no comparison.

The trial room was then deleted at the Owner's word: its folder removed, and `export room.ch01_dungeon_r02_pass --prune`
took its 8 files and Manifest out of the game. The palette proposals stay in `.kiripix/palette-proposals/` for r02.

**Tokens:** not recorded. The session can't read its own count, and the Owner closed the ticket without it
(2026-11-19). The room was a redo of dungeon r02 rather than a new ch01 room, because no new Source was painted (the
Owner's choice).
