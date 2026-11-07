---
status: done
milestone: M2
agent: none
type: trial
parent: 0037-m2-layers-and-props.md
depends_on: [0036-m2-flood-does-nothing-on-a-painted-plate.md, 0059-m2-slow-click-to-segment.md, 0060-m2-room-border.md, 0061-m2-ui-room-border.md]
---

# M2: trial: does a Claude first pass save the Owner time?

Spec §2 (principle 3) and §14 (M4). Story 21 of [0037](0037-m2-layers-and-props.md). The Owner wants Claude's help in preparing
rooms, and asked to plan it around the time-per-room measure. The risk is that correcting a poor first pass takes longer than
doing the work by hand, so test that on a real room before building for it.

This needs no MCP: the CLI already does everything a first pass needs. It runs in a main session with the Owner, with no
subagent and no new code. If it needs a Command that doesn't exist, record that as the result rather than build it here.

## What to do

1. Take a real room of about the harbour's complexity that the Owner hasn't prepared. Import and fit it.
2. Claude does the first pass with the CLI and looks at the room through `kiripix preview`: `solid` and `pit` Masks by clicks,
   floods and the border, then Spawns and Exits. It works to a set token budget, agreed at the start.
3. Claude never accepts: `accept` stays the Owner's. A `needs-review` Stage waits for them.
4. The Owner corrects the room in the UI to a finish they'd ship, and notes their own total time.

## What to record, in this ticket

- The Owner's time on this room, against their time on the gate's hand-made reference room ([0058](0058-m2-gate.md)).
- How much of the first pass survived: Decisions kept against undone or added, from the journals.
- The tokens and money it cost, and where Claude went wrong: which object types, and which Commands were missing or awkward.
- A recommendation for M4: build on this, narrow it (for example to Markers only, or to a first `solid`), or drop it.

## Acceptance criteria

- [x] One real room done this way, with the numbers above recorded.
- [x] The Owner's call is recorded in the gate, [0058](0058-m2-gate.md).

## Handover line (2026-11-06)

The line between Claude's first pass and the Owner's corrections. Everything in these journals up to and including the
last Decision ID is Claude's.

| Room | `masks.jsonl` lines | Last `masks` Decision | `place.jsonl` lines | Last `place` Decision |
|---|---|---|---|---|
| `room.ch01_dungeon_r01` | 49 (42 brush, 1 border, 3 flood, 3 undo: 43 kept) | `01M6RTCPD2FFA5H1PNJ4S3MCQX` | 3 | `01M6RTCT5YR050WRYJNETECYPM` |
| `room.ch01_dungeon_r02` | 12 (11 brush, 1 border) | `01M6RTF5N7VETF2XXGZZP5KCR5` | 3 | `01M6RTF9A2QNW5M3KFGEV42NJD` |
| `room.ch01_dungeon_r03` | 37 (36 brush, 1 border) | `01M6RTQ33BPM0RX6RPV1DWQW2G` | 3 | `01M6RTJYDJC5WGK5FQGB4Y7FXN` |

Claude's own undos: 3, all on r01, the floods. No clicks were recorded in any room. Each room's Exits point at each other
as placeholders.

Tokens at the handover, fresh = input + cache writes + output: about 62k for r01, of which 24.5k was reading in at the
start; about 13k for r02; about 25k for r03; 54k for one price lookup that loaded a large skill. Total 156.5k of 300k.
Cache reads 1.78M.

## Result

Three rooms on one Owner's review: `solid` and `pit` Masks, Spawns and Exits, with no Layers. It saved a great deal of time on
these rooms. It doesn't yet show the same for Layers, or for rooms with less regular shapes.

**The Owner's time** (reviewing and correcting):

| Room | Time | What it went on |
|---|---|---|
| r01 (scored) | 20 s | Review; no edits |
| r02 | 60 s | Review, and one correction to the bench |
| r03 | 50 s | Review; no edits. The unreachable corner is accepted for now |
| **Total** | **130 s** | |

Against the M1 baseline, 13.4 minutes of real work on a rough pass of one room, r01 took about 2.5% of that time. The baseline
is only a stand-in until [0058](0058-m2-gate.md) has the hand-made reference room. It was the Owner's first time with the tool,
and on a different room. It's a fair match in one way: M1's `layers` was a pass-through, so neither figure includes Layers.

Not in these times: testing the walk, which the Owner confirmed is excluded and said took most of their time, with no figure
recorded. So 130 s isn't the whole cost of a room, and a figure for a whole room needs the walk test added. Claude's own elapsed
time isn't counted either.

**Survival**, compared by decision name and data. No `accept` was needed, so the IDs didn't change:

| Room | Kept | Undone by the Owner | Added by the Owner |
|---|---|---|---|
| r01 | 43 `masks`, 3 `place` | 0 | 0 |
| r02 | 12 `masks`, 3 `place` | 0 | 2 (erase strokes on the bench, one correction) |
| r03 | 37 `masks`, 3 `place` | 0 | 0 |

101 of 101 Decisions kept; 2 added. Claude's own undos: 3, the floods on r01. There was no Exit retargeting. The Owner confirmed
that the Exits were placed correctly and that r03's Masks were right.

**Tokens:** about 62k on r01 (24.5k of it reading in at the start), 13k on r02, 25k on r03, and 54k on a price lookup that the
trial didn't need. About 100k of fresh tokens for three rooms, against a budget of 300k.

**Where Claude went wrong:**

- **An object that isn't rectangular:** a box painted over the r02 bench, which Claude also misread as a radiator. It's the one
  correction in the trial.
- **Dark painted surfaces:** at tolerance 0.04, floods on r01's pits and margin gave speckle over part of the region. Claude
  tried no other tolerance, and no flood on r02 or r03, so this isn't evidence against floods in general.
- **Clicks:** none recorded, as boxes were cheaper on these straight-edged rooms. Of 16 probes, pylons, railings, planters and
  the pits came close to the painted boxes; the booth came back in fragments and the floor as one tile.

**Missing or awkward Commands**, now tickets:

- No polygon Decision, though the `masks` description names one: [0072](0072-m2-polygon-decision.md). Zigzag strokes stood in.
- Coordinates judged by eye, and no view of where the Body fits: [0073](0073-m2-preview-region-grid-walkable.md).
- No way to try a flood without recording it, and `segment-preview`'s runs are huge: [0074](0074-m2-flood-preview-and-probe-summary.md).
- `decide` returns every current Decision on every call, which is about 444 KB over r01's Decisions: [0075](0075-m2-decide-in-bulk-and-briefly.md).
- Clicks must come last because `reach` can't run on a pending click: [0078](../0078-m3-reach-probe.md).

**Recommendation for M4: build on this, for `solid`, `pit` and Markers.** Correcting took far less time than doing the work by
hand, and almost nothing was thrown away. Give the first pass the game's room map too, so that Exits get their real targets
rather than placeholders; the Owner expects to provide one.

Don't extend it to Layers on this evidence. Layers weren't tried, a Layer's edge is visible where a Mask's isn't, and the `click`
path wasn't exercised at all. These were also three rooms from one set, mostly straight-edged, which suits boxes. Test Layers
separately first.
