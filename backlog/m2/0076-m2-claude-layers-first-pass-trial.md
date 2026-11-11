---
status: done
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

### Handover line (2026-11-06)

Everything in these journals up to and including the last Decision ID is from before this trial. r02's `masks` line includes
the Owner's 2 erase strokes. No room had a `layers.jsonl` when the trial began.

| Room | `masks.jsonl` lines | Last `masks` Decision | `place.jsonl` lines | Last `place` Decision | `layers.jsonl` |
|---|---|---|---|---|---|
| `room.ch01_dungeon_r01` | 49 | `01M6RTCPD2FFA5H1PNJ4S3MCQX` | 3 | `01M6RTCT5YR050WRYJNETECYPM` | none, 0 lines |
| `room.ch01_dungeon_r02` | 14 | `01M6S14P595Z00MNSWV4HQ86G3` | 3 | `01M6RTF9A2QNW5M3KFGEV42NJD` | none, 0 lines |
| `room.ch01_dungeon_r03` | 37 | `01M6RTQ33BPM0RX6RPV1DWQW2G` | 3 | `01M6RTJYDJC5WGK5FQGB4Y7FXN` | none, 0 lines |

### First pass, as counted during the work (2026-11-07)

Before the Owner's corrections. No room has been accepted, so nothing after `layers` has run on these Layers.

| | r02 (scored) | r03 | r01 |
|---|---|---|---|
| Layers | 5 | 16 | 2 |
| Probes | 19 | 57 | 14 |
| Clicks | 16 | 49 | 2 |
| Trims | 7 | 3 | 0 |
| Claude's own undos | 0 | 0 | 0 |
| Y-sort lines recorded (`above`: none) | 5 | 16 | 2, one then moved 1 px |
| `layers.jsonl` lines | 23 | 52 | 2 |
| `place.jsonl` lines | 8 | 19 | 6 |
| Lift, wall time per `run --rerun` | 35.5 s, 34.5 s, 4.9 s | 48.7 s, 42.7 s, 10.5 s | 29.9 s |
| Fresh tokens | 46.9k, plus 35.3k reading in | about 32.7k | about 16k |
| Mean luma of the fit image | 34.7 | 46.4 | 28.9 |

Left out, on purpose: litter and papers (flat), r03's bottles (too small to hide a Body), wall posters and signs, and r01's vertical
stair-side pipes (part of the stair wall, and clicks there leak to 10k to 17k pixels).

**Runner time:** SAM 2 about 0.65 to 0.83 s for the first click of a run, then about 0.07 s. LaMa about 0.9 to 1.1 s first, then
about 0.25 s. A probe takes about 4 s, and its answer says the embedding was `computed` every time. A lift takes far longer than
its Runner calls: about 23 s passes between the last SAM 2 call and the first LaMa call in `history.jsonl`, unexplained here. The
Stage's own `duration_s` (0.4 to 2 s) leaves the Runner time out.

**Fragments, for 0079** (a single-click probe returning only part of the object, or leaking beyond it):

- r02: 11 of 14 single-click probes. Only the bench, and the machine from one lucky point, came whole.
- r03: the booth 9 of 9 and the post 2 of 4, and one rail ran into a pylon. Benches, planters, railings, the bin and all ten pylons
  came whole first time. Arms and bars came back as separate clean pieces, 17 clicks' worth.
- r01: 12 of 14. 8 leaked into the pit side, 4 returned a corner. 2 points gave the whole railing.

**Missing or awkward:**

- A multi-click probe doesn't predict the lift. On r02's lockers the same 6 clicks gave 13,471 px as a probe and 11,980 px as a
  Layer, with two door tops missing. `run` makes one Runner call per click, so each click looks segmented alone and then unioned.
- `trim` only removes. r03's arm-to-pylon joints, about 2 to 3 px each, stay in the Plate: a click there returns the whole pylon.
- `preview` can't show one Layer's alpha, or brighten a dark room. Claude drew both in a scratch script, at 1.8× brightness, because
  edges were hard to judge otherwise.
- `check` returns no findings while `place` is stale, so a clean result says nothing about the new y-sort lines.

**Darkness** (the Owner raised it during the trial): a factor to score with the Owner's times. r02's dark machine and bin segmented
fine; r01, the darkest, leaked most, though its pipes also touch the pit side, so that isn't darkness alone. Darkness also hides
the Plate's fill on r01, and the Layer's edge along with it.

**Against the existing Masks,** before any rerun: nearly all of each Layer lies on `solid` or `pit`, except r03's `arms` (95% on
walkable ground), `post` (20%) and the rails (9% to 14%). So the Body can walk through the turnstile arms as the Masks stand.

**The Plate:** fills are object-shaped ghosts, not clean floor: r03's pylons 5 to 7 and r02's machine and bin stay as dark shapes.
They sit behind opaque Layers of the same shape, so they should only show at a rim. That needs the Owner's eye.

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
- **Evidence for other tickets:** how often a click returned fragments, for [0079](../m3/0079-m3-segment-with-a-box.md), and how much
  the wait for `accept` got in the way, for [0078](../m3/0078-m3-reach-probe.md).
- **A recommendation for M4:** extend the first pass to Layers, narrow it (for example to separate solid objects, or to y-sort
  lines on Layers the Owner lifts), or leave Layers to the Owner. Say plainly if correcting took longer than doing it by hand.

## Acceptance criteria

- [x] r02 done this way, with the numbers above recorded.
- [x] The Owner's call on Layers for M4 is recorded here.

## Result

Three rooms on one Owner's review. The first pass clearly saved time on r03, the room with many objects, and didn't on r01, the
room with few, dark ones. Every Decision survived, but survival overstates the result here: the Owner kept Layers they didn't need,
because a Layer that does no harm costs nothing to leave. The first pass's weakness is choosing what to lift, not lifting it.

**The Owner's time:**

| Room | Reviewing and correcting Layers | Judging the Plate | Testing the walk | Layers |
|---|---|---|---|---|
| r02 (scored) | 50 s | With the Layers, not timed apart | 10 s | 5 |
| r03 | 100 s | With the Layers, not timed apart | 50 s | 16 |
| r01 | about 360 s, see below | With the Layers, not timed apart | 12 s | 2 |

- **r03** took 100 s against the Owner's estimate before the trial of 20 to 30 minutes by hand. Afterwards the Owner put the saving
  at "10-12 minutes at least", since lifting by hand in the UI is slow even with a warm Runner. Both are estimates. Correcting took
  far less time than doing it by hand.
- **r02:** no comparison, because [0058](0058-m2-gate.md) has no Layer time yet. The Owner also described it as about a minute.
- **r01** isn't a time for correcting Claude's work. It's mostly the Owner trying to lift the rails at the top of the stairs, which
  Claude hadn't lifted, and giving up. The Owner first gave both 300 s and "more than 6 minutes", and settled on 6 minutes. SAM 2 did
  badly on this dark image for both of them, and the Owner expects to redraw the room, suspecting its palette or the JPEG
  conversion. Afterwards the Owner concluded the rails could simply stay in the `solid` Mask, with no Layer, which would have been
  easier.
- **Not separable:** the wait for `accept`, which the Owner found long on every room, may or may not be in these times.
  `history.jsonl` doesn't record it.
- **Claude's own elapsed time** isn't counted, as in 0062.

**Survival,** by name and data since `accept` re-records:

| Room | Layers kept | Redone | Removed | Added by the Owner | Decisions kept | Undone by the Owner | Added by the Owner |
|---|---|---|---|---|---|---|---|
| r02 | 5 of 5 | 0 | 0 | 0 | 23 `layers`, 5 `place` | 0 | 0 |
| r03 | 16 of 16 | 0 | 0 | 0 | 52 `layers`, 16 `place` | 0 | 0 |
| r01 | 2 of 2 | 0 | 0 | 2 (`layer1`, `layer3`) | 2 `layers`, 3 `place` | 0 | 4 clicks |

101 of 101 kept; Claude's own undos 0. **What the Owner would rather not have lifted:** r01's two lower rails, because the Body is
always drawn over them, and perhaps r03's booth. The Owner left r02's bench lifted once it was shown to have no transparent pixels
(0 partial alpha, 0 holes). So at least 2 of the 23 Layers did nothing, though the journals record them as kept.

**Quality, by object type:**

| Object type | Edge | Y-sort line |
|---|---|---|
| Separate solid objects (benches, planters, bins, r02's machine and extinguisher) | Accepted. Most took 1 or 2 clicks; the machine and bench needed trims | No line changed |
| Repeated thin objects (r03's pylons, rails, railings) | Accepted. One click each, nearly identical | No line changed; the Owner praised r03's sorting |
| Compound objects (turnstile arms and bars, post) | Accepted, in a Layer apart from the pylons with its own line; the Owner named the arms as done right | Right, walked in r03 |
| Many-surface objects (lockers, booth) | Accepted, 8 clicks for the lockers and 6 for the booth. Leaves gaps: 25 and 198 enclosed px, behind solid ground | Booth perhaps not needed |
| Thin objects on a dark ground (r01's lower rails) | Accepted, but not needed | Unneeded: the Body is always on top |

**The Plate:** the Owner found inpainting quite noticeable on r02 and r03, but doesn't expect to need it in those rooms, because the
Layers cover it. In the Owner's view, inpainting works well only on small or narrow objects with distinct colours. Judging the Plate
isn't a separate task: the Owner did it alongside the Layers and says it should stay part of the overall Layers check, so later
trials need no separate figure for it.

**Masks after a lift:** no repainting. `masks.jsonl` is unchanged in all three rooms (49, 14 and 37 lines), and `masks` rebuilt
without review. All 3 rooms ran through to `export` after `accept`.

**After `accept`:** r02 has no findings. r03 has its known unreachable corner and 3 `reach.narrow_gap` infos. r01 has 2
`layer.no_ysort` errors, for the Owner's `layer1` and `layer3`, which are still in its journal. `layer1` is 26,630 px in 90 pieces,
so it took much of the room out of the Plate. r01's status still shows `export` as `done` alongside those errors, which is worth a
look in case the Stage should have stopped.

**Tokens:** 46.9k for r02 plus 35.3k reading in, about 32.7k for r03, about 16k for r01, 11.5k on the handover: 142.4k. Closing the
ticket and writing 0083 took the total to about 207k, against a budget of 300k. None was spent on a price lookup. Per Layer, r03 cost 2k and r02 9k,
so the larger room was the cheaper one.

**Evidence for other tickets:**

- **[0078](../m3/0078-m3-reach-probe.md):** the wait got in the way less than expected. Clicks and lines all had to go in unconfirmed, and
  after `accept` no line or Marker needed changing, so here it cost a longer handover list and nothing else. One trial on rooms with
  good Masks, so it doesn't rule the ticket out.
- **[0079](../m3/0079-m3-segment-with-a-box.md):** fragments are common but concentrated: r02 11 of 14 single-click probes, r01 12 of 14,
  r03's booth 9 of 9, against r03's 20-odd whole objects. On r01 a shift of a few pixels decides it: 135,459 leaks to 8,841 px where
  142,460 is the clean rail. The Owner's clicks at y≈102 did the same: 142,102 and 271,102 gave `layer1`'s leak, 134,101 and 268,103
  a thin band. A box may help there, and it's where the Owner lost the time. Untested.
- **For choosing Layers by numbers:** a test of how much reachable ground puts the Body behind each Layer didn't separate the
  Layers worth lifting: r01's unneeded rails score 108 and 144 px, about the same as Layers the Owner kept. It ignored the Body's
  footprint, so it doesn't show that such a test can't work, only that this one doesn't.
- **[0083](../m3/0083-m3-ui-show-that-work-is-happening.md), new:** `accept` gives no sign of working in the UI, and neither does lifting a
  Layer or drawing a Mask. The Owner clicks, can't tell whether it's running, and clicks again.

**Recommendation for M4: extend the first pass to Layers, narrowed, for rooms with many objects.**

- **Keep:** clicks and y-sort lines on separate solid, repeated and compound objects in rooms with enough contrast. That's where the
  time went and where the pass held up, and it needs no probing beyond what this trial did.
- **Change:** Claude proposes the list of Layers first, each with the reason the Body can go behind it, and the Owner cuts the list
  before any click. Lifting what doesn't need it cost little here, but the pass also missed what the Owner did want: the upper rails.
- **Leave to the Owner, or fix the image first:** rooms like r01, dark with thin objects touching their surroundings. Neither Claude
  nor the Owner did well there, and it may be the image rather than the method.

It rests on one Owner, one set of rooms, and a by-hand figure that's an estimate for r03 and absent for the others, so 0058's Layer
time should be set beside it when there is one.

**The Owner's call for M4 (2026-11-07): keep improving the first pass on Layers.** In the Owner's words, it "works fine, but only on
certain clearly distinguishable objects", and the quality of the source image is important. Claude "mostly did well" on these three
rooms, on average it would save them time, and it's "worth continuing improving". The proposed list of Layers above is Claude's
suggestion, which the Owner hasn't ruled on.
