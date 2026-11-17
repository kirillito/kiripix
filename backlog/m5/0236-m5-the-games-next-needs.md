---
status: todo
milestone: M5
type: spec
---

# M5: what the game needs next, then character layers

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §1 (non-goals), §6, §14 (M5, Later) and §16 (open decisions 8 and 9). The
game's list of what it needs from Kiripix, ordered by when, was written at the M4 gate (2026-11-16) from
`../urban-mystery-club/docs/ROADMAP.md` and `docs/MILESTONE_PLANS.md`. This ticket turns it into M5's order. The layers spec
stays [0152](0152-m5-character-layers.md).

## Problem Statement

M5 was planned as character layers, which the game needs only at its M11. The game is at its M03 (the 3D MC). In the next
three game milestones (about six weeks of the Owner's time) it needs things Kiripix doesn't have:

- something held in the hand (the phone, a rake, class weapons, an instrument);
- one clip timing on every body;
- dialogue portraits, at its M04, the next milestone;
- bins that topple.

Its M07 to M10 need a few more: item icons, a decision on tiles for the dungeon corridors, normals for painted tunnels,
traversal spots and Looks that bring their own lights. The game's top risk is room throughput (a chapter is about 30 rooms,
at about one room per milestone today, with a $0 budget), so M5 also keeps cutting the Owner's time per room, and the test
suite's 80–90 minutes.

## Decided (the Owner, 2026-11-16)

1. **The game's near needs go first in M5**, and layers go last. No milestone before M5.
2. **0170's (a) or (c)** is settled in [0238](0238-m5-held-things-trial.md), moved out of the layer trial.
3. **Motion for 2D sprites from a still is out:** it's animation authoring (spec §1). The game tweens a sprite, and a pose
   made as an image-model edit imports as a one-frame clip of a `sprite`.
4. **Prop states are supported, any number of them** ("There might be more than two, why not support several?"):
   [0257](0257-m5-prop-states.md).
5. **Wave 4 stays in M5.**
6. **Portraits have their own colours,** not the Project palette and not the Ramp table: they're generated, they have
   gradients, and they shouldn't depend on the character sprites ([0240](0240-m5-portrait-kind.md), question 3). This is an
   exception to principle 6, recorded in spec §2.

## Order

| Wave | Game need | Tickets |
|---|---|---|
| 1 | M03–M04, now | [0237](0237-m5-render-records-named-points.md) points per frame, [0239](0239-m5-project-clip-table.md) the clip table, [0238](0238-m5-held-things-trial.md) the held-things trial, [0241](0241-m5-portrait-trial.md) the portrait trial, [0274](0274-m5-set-colours-op.md) the set's colours, [0250](0250-m5-m4-gate-small-findings.md) the gate's small findings, [0235](0235-m5-settings-writes-keep-comments.md), [0233](0233-m5-acceptance-test-agent-never-stops-at-the-room.md); test speed: [0275](0275-m5-tests-build-a-room-once-per-module.md), [0277](0277-m5-start-faster-pydantic-and-typer.md); [0278](0278-m5-a-stage-code-change-makes-it-stale.md) a Stage's code version |
| 2 | M04–M06 | The portrait Kind [0240](0240-m5-portrait-kind.md) (0242 to 0245); Prop states [0257](0257-m5-prop-states.md) (0258 to 0261); the build tickets 0238 files; [0234](0234-m5-sprite-style-and-size-trial.md) sprites beside the bodies; [0232](0232-m5-look-edit-of-a-piece-or-crop.md); [0246](0246-m5-inner-lines-at-a-depth-step-op.md) and [0247](0247-m5-finish-inner-lines-at-a-depth-step.md) inner lines inside a part; the room's time: [0249](0249-m5-room-first-pass-workflow.md), [0279](0279-m5-settle-an-areas-cells.md), [0280](0280-m5-palette-suggest-from-a-room.md), [0286](0286-m5-suggest-foreground-layers-trial.md); the UI: [0282](0282-m5-ui-clip-controls.md), [0284](0284-m5-ui-show-points-on-the-frames.md); [0281](0281-m5-real-blender-tests.md) real-Blender tests |
| 3 | Answers before M08–M10 | [0251](0251-m5-tileset-trial.md) the tileset trial (no code), [0252](0252-m5-environment-normals-trial.md) environment normals, the `icon` Kind [0253](0253-m5-icon-kind.md) (0262 to 0264), [0248](0248-m5-snapshots-for-trials-across-a-cast.md) snapshots for trials across a cast |
| 4 | M10–M11 | Looks part 2 [0254](0254-m5-looks-markers-combining-and-reach.md) (the ADR 0269, which files the work tickets once the Owner accepts it); traversal Links [0255](0255-m5-traversal-links.md) (0265 to 0268); layers, [0152](0152-m5-character-layers.md) and the work tickets 0153 files |
| Gate | | [0256](0256-m5-gate.md) |

A wave is a priority, not a barrier: a later wave's ticket with no dependency may start early when an agent is free. Within
a wave, mind the `depends_on` fields. Tickets that touch `kiripix/recipes/clips.py` or `render_frames.py` (0237, the 0238
build, 0281) shouldn't run at the same time.

## What can run without the Owner

Coded and tested by an agent alone, with at most an eye check at the end:

| Area | Tickets |
|---|---|
| core | 0239, 0242, 0248, 0250, 0258, 0265, 0277, 0278, 0279, 0280, 0235 |
| imaging | 0243, 0246, 0259, 0262, 0266, 0274 |
| character | 0237, 0247 (code; the Owner picks the default) |
| export | 0244, 0260, 0263, 0267 |
| UI | 0245, 0261, 0264, 0268, 0282, 0284 |
| tests | 0275, 0281, 0233 |

These need the Owner's eye or choice: the trials 0238, 0241, 0234, 0251, 0252 and 0286 (the last runs alone up to its overlays),
the ADR 0269, 0249's measured room, and 0232's real edit.

## The game's items, one by one

| # | Item (game milestone) | Result |
|---|---|---|
| 1 | Things held in the hand (M03, M05, M06) | **Filed** [0237](0237-m5-render-records-named-points.md) (points per frame) and [0284](0284-m5-ui-show-points-on-the-frames.md) (their UI). **Trial first** [0238](0238-m5-held-things-trial.md): (a) or (c), the grip, the colours and the cell. Its build tickets come from it. |
| 2 | A `portrait` Kind (M04) | **Trial first** [0241](0241-m5-portrait-trial.md) (its prototype is also the game's fallback script). **Filed** the spec [0240](0240-m5-portrait-kind.md) and 0242 to 0245 and [0274](0274-m5-set-colours-op.md). |
| 3 | Prop states (M05–M06) | **Filed**, any number of states: [0257](0257-m5-prop-states.md) and 0258 to 0261. |
| 4 | One clip timing for every body (M03) | **Filed** [0239](0239-m5-project-clip-table.md). Bases don't make it moot: the MC's two bodies are two bases. |
| 5 | Motion for 2D sprites from a still (M05) | **Dropped:** animation authoring, a non-goal (spec §1). The game tweens. |
| 6 | Traversal Markers (M10) | **Filed** [0255](0255-m5-traversal-links.md) and 0265 to 0268. |
| 7 | Looks, the rest of open decision 8 (M10) | **Filed** [0254](0254-m5-looks-markers-combining-and-reach.md) and the ADR draft 0269. The work tickets are filed once you accept the ADR, so they follow it. |
| 8 | Environment normals from depth (M10) | **Trial first** [0252](0252-m5-environment-normals-trial.md). |
| 9 | The tileset trial with no code (before M09) | **Trial first** [0251](0251-m5-tileset-trial.md). |
| 10 | An `icon` Kind (M08) | **Filed** [0253](0253-m5-icon-kind.md) and 0262 to 0264. |
| 11 | Named terrain Masks | **Later**, already in spec §14. Nothing changes until the M09 platform asks. |
| 12 | Layers: what the game needs from them | Added as inputs to [0152](0152-m5-character-layers.md) and [0153](0153-m5-character-layer-trial.md). |
| 13 | Inner lines where a part crosses itself | **Filed** [0246](0246-m5-inner-lines-at-a-depth-step-op.md) and [0247](0247-m5-finish-inner-lines-at-a-depth-step.md). |
| 14 | Setting trials across a cast | **Filed** [0248](0248-m5-snapshots-for-trials-across-a-cast.md). |
| — | Claude's first pass as a workflow | **Filed** [0249](0249-m5-room-first-pass-workflow.md). |
| — | A batch view for many rooms | **Later**, unchanged: the status board already lists every Asset by Kind and Stage. |
| — | `stats` on every room and character | In the gate, [0256](0256-m5-gate.md). |

## Out of scope

- The game's own work: its portrait UI, its compositor, its tweens, its tile kit.
- Generation through a Provider (M6), including `gen` for a portrait's emotions or a Prop's states.
