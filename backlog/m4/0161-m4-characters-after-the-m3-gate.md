---
status: todo
milestone: M4
type: spec
---

# M4: characters after the M3 gate

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6.3 and §14 (M4), and the Owner's notes at the M3 gate
([0117](../m3/0117-m3-gate.md), signed off 2026-11-11). Builds on M4's palette ramps per part
([0147](0147-m4-character-palette-ramps.md)), whose material pass ([0148](0148-m4-render-material-pass.md)) two of these
tickets need.

## Problem Statement

The first real character, `character.mc02`, plays in Godot and "looks very impressive", but the gate found four things to
adjust:

1. Mixamo's clips are longer than the game needs (idle: 100 frames, where the game wants 10 to 20), and a decided clip can't be
   changed without undoing every clip after it.
2. One clip snaps into the next, with no transition.
3. Small parts, the eyes above all, vanish in some frames.
4. Beside the painted rooms, the character reads as pixelated 3D, not as 2D pixel art.

## Solution

| # | Ticket | Kind |
|---|---|---|
| 1 | [0156](0156-m4-edit-a-clip.md) (the Decision), then [0157](0157-m4-ui-edit-a-clip.md) (the clips screen) | work |
| 2 | [0158](0158-m4-transition-clips-trial.md) | trial: the Owner picks how transitions are made |
| 3 | [0159](0159-m4-part-vanishes-check.md) | work, after 0148. The Owner's own fix is bigger eyes in the Model |
| 4 | [0160](0160-m4-flatter-character-look-trial.md) | trial, after 0148 (and better after 0150): the Owner picks the options to build |
| - | [0162](0162-m4-render-measures-meshes-that-dont-render.md) | a bug found while closing M3 |

Added 2026-11-12 for the game's M03 (four character Assets: 2 bodies x 2 outfits, a battle-clip set per class, one swap shader):

| # | Ticket | Kind |
|---|---|---|
| 5 | [0170](0170-m4-weapon-in-a-battle-clip-trial.md) | trial: how a class's weapon gets into its battle frames (blocks the game's M03-02) |
| 6 | [0171](0171-m4-copy-clips-from-a-character.md) | work: copy clip Decisions between characters, until M5's bases (0165). Chosen by the Owner on 2026-11-12 over pulling 0165 forward |
| 7 | [0172](0172-m4-foot-contact-frames.md) | work, lower priority: foot contact frames in `character.json` |

Ramps that match across the four characters are a spec of their own, [0166](0166-m4-ramps-match-across-characters.md), after
0147's tickets.

A trial files its build tickets here when the Owner has chosen.

## Order

The game's M03 waits on 0156 (its idle is 10 to 20 frames), 0160 (the Owner approves its look beside the painted rooms) and
0170 (one attack per class), so these go as early as their dependencies allow, ahead of the rooms work.

| Wave | Tickets |
|---|---|
| 1 | **0156 first**, then 0162 and the trials 0158 and 0170 (prototypes outside `kiripix/`, so no shared files) |
| 2 | 0157; **the trial 0160 as soon as 0148 is done** (its options 1, 2, 4 and 5 need only the material pass; option 3, part ramps, joins when 0150 lands); 0159 after 0148 |
| 3 | 0171 (after 0156); the build tickets 0158, 0160 and 0170 file |
| 4 | 0172 (after 0156 and 0151); moves to M5 if M4 is full |

**Don't run these at the same time, because they edit the same files:**
- 0162 and 0148 (`kiripix/blender/render_frames.py`).
- 0156 and anything else in `kiripix/recipes/clips.py`: 0170's build ticket and 0172 too.
- 0172 and 0151 or 0169 (`character.json`).

## User Stories

1. As the Owner, I want to change a clip's frame range after deciding it, keeping its name, so that a long Mixamo clip can be cut
   to what the game plays.
2. As the Owner, I want transitions between clips, made once and named like any clip, so that an idle character doesn't snap
   into an attack.
3. As the Owner, I want to be told which frames lose a small part, so that I know what to fix in the Model.
4. As the Owner, I want a character style that sits with the painted rooms, so that characters don't look like 3D renders.
5. As the game, I want each class's weapon in its battle frames, so that the three classes look different in a fight.
6. As the Owner, I want to decide a clip once for four bodies, so that four bodies don't mean deciding every clip four times.
7. As the game, I want the frames where a foot plants, so that footsteps play without marking every clip by hand.

## Out of scope

- The game's animation state machine (when to play an idle on a timer, which transition to pick).
- Base Models made by Claude in Blender, and characters sharing a base's rig and clips: M5
  ([0164](../m5/0164-m5-claude-built-base-models-trial.md), [0165](../m5/0165-m5-characters-share-a-base.md)); 0171 is only
  a stop-gap for the clip Decisions.
