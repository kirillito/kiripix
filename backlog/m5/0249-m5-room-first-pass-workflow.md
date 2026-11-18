---
status: todo
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
- [ ] A fresh session with the skill takes the next ch01 room (not `harbor_front`) through its first pass. Its tokens and
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
