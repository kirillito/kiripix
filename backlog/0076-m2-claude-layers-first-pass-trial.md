---
status: todo
milestone: M2
agent: none
type: trial
parent: 0037-m2-layers-and-props.md
depends_on: [0062-m2-claude-first-pass-trial.md, 0073-m2-preview-region-grid-walkable.md, 0074-m2-flood-preview-and-probe-summary.md, 0075-m2-decide-in-bulk-and-briefly.md, 0077-m2-grow-the-palette-from-an-image.md]
---

# M2: trial: does a Claude first pass on Layers save the Owner time?

Spec §2 (principle 3) and §14 (M4). Follows [0062](0062-m2-claude-first-pass-trial.md), where a first pass on `solid`, `pit` and
Markers took the Owner 130 s of correcting across three rooms, and kept every Decision. That trial left Layers out, and recorded
no clicks at all. So this tests what it couldn't. A Layer's edge shows on screen where a Mask's doesn't, and lifting has only
one route, the `click`, so boxes can't stand in here. The risk is the same as before: correcting a poor pass may take longer
than doing it by hand.

It runs in a main session with the Owner, with no subagent and no new code. A Command that's missing or awkward is a result.

## Agreed at the start

- **Token budget:** 300,000 fresh tokens in all, at most 150,000 by the end of the first room. Fresh means input + cache writes +
  output, summed from the session's `.jsonl`, each distinct `message.id` once. Stop at the limit, even mid-room; running out is a
  result. Tokens only, no money.
- **No time baseline:** the Owner accepts that there's none for Layers. Their estimate for doing r03 by hand, before the trial, is
  20 to 30 minutes in GPU mode, mostly on the turnstiles' detail. It's an estimate, not a measurement, but it's the figure to set
  r03's result beside.
- **Rooms, in this order,** going on only if under budget. They already have Masks and Markers from 0062:

| Order | Asset | Layers to try | Why |
|---|---|---|---|
| 1 (scored) | `room.ch01_dungeon_r02` | Lockers, machine, bench, extinguisher, bin | Medium; separate solid objects |
| 2 | `room.ch01_dungeon_r03` | Booth, pylons with arms, central post, side railings, vertical rails, benches, planters, bin | Hardest; thin and compound objects |
| 3 | `room.ch01_dungeon_r01` | South pit-lip pipes | Few, but thin and on a dark ground |

Claude may leave out an object it judges not worth lifting, and says why.

## Hard limits

Never accept, never set `KIRIPIX_TEST_OWNER` or `KIRIPIX_TEST_RECIPES`, and never work around `owner.required`. No `kiripix export`,
no commit or stage in either repo, and no change to `room.harbor_front`. No Kiripix code changes. No new Masks or Marker moves
beyond what lifting needs: changes to those are the Owner's, or are noted for them.

## Before the first Decision

Save in this ticket each room's Decision count and last ID in `decisions/masks.jsonl`, `place.jsonl` and `layers.jsonl`. That's
the line between earlier work and this trial, and it includes the Owner's erase on r02.

## Order of work

`layers` comes before `masks`, `place` and `reach`, and a click needs `run --rerun`, so `layers` lands in `needs-review` and stops
everything after it until the Owner accepts. What Claude can check before that is part of the trial.

1. **Look.** Use `preview` with `--region` on each object. Say which you'd lift, and what you doubt.
2. **Probe before each click.** Use `probe segment-preview <asset> x,y --summary`, against the box you'd expect.
3. **Click, and rerun.** Record the clicks a Layer needs, in one batch where possible, then `run <asset> layers --rerun`. Compare
   the result with `preview`, `undo` what's wrong, and `trim` a rim.
4. **Sort.** Record a y-sort line for each Layer in `place`, or `above` for one that's always above the Body.
5. **Hand over,** listing what `layer.no_ysort`, `marker.*` and `reach` haven't been able to confirm.

## What to record, in this ticket

- **The Owner's time, per room, with each part separate:** reviewing and correcting Layers; judging the Plate; and testing the
  walk, which 0062 left unmeasured. Show r02 separately. There's no M1 baseline for this, since M1 had no Layers, so compare
  with the gate's hand-made reference room ([0058](0058-m2-gate.md)) once it has a Layer time. Until then, say that there's no
  comparison.
- **Survival:** Layers kept, redone, added and removed, and Decisions kept, undone and added since the line. `accept` re-records
  clicks under new IDs, so compare by name and data. Count Claude's own undos separately.
- **Quality, by object type:** whether the edge and the filled Plate were acceptable, and whether each y-sort line was right.
- **Masks after a lift:** whether `brush` and `border` Masks came through the changed Plate with nothing to review, as their
  schemas imply, and whether anything needed repainting.
- **Tokens,** per room, and Runner time per click and per lift.
- **Evidence for other tickets:** how often a click returned fragments, for [0079](0079-m3-segment-with-a-box.md), and how much
  the wait for `accept` got in the way, for [0078](0078-m3-reach-probe.md).
- **A recommendation for M4:** extend the first pass to Layers, narrow it (for example to separate solid objects, or to y-sort
  lines on Layers the Owner lifts), or leave Layers to the Owner. Say plainly if correcting took longer than doing it by hand.

## Acceptance criteria

- [ ] r02 done this way, with the numbers above recorded.
- [ ] The Owner's call on Layers for M4 is recorded here.
