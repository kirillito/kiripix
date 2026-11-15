---
status: done
milestone: M4
agent: character-pipeline
type: ticket
parent: ../m5/0152-m5-character-layers.md
depends_on: [0164-m4-claude-built-base-models-trial.md]
---

# M4: characters made from a base share its rig and clips

Spec §6.3 (model, rig, clips). From the M3 gate ([0117](../m3/0117-m3-gate.md)): "if I figure out how to build 3D models
faster, or at least build a base collection of those models, moving forward it will get easier to build new characters."

## The gap

Each character today does the whole round trip on its own: import the Model, upload it to Mixamo, auto-rig, find and download
each animation, import the rigged file and every clip source, and decide every clip. On mc02 the Mixamo round trip alone was
16 minutes of the journal. NPCs and enemies built on the same body (with another head, hair or outfit, and the same skeleton)
repeat all of it.

M4's stop-gap (chosen by the Owner on 2026-11-12) [0171](0171-m4-copy-clips-from-a-character.md) (`kiripix clips copy`) already copies
clip Decisions between characters, with no link. A base replaces it: decide whether `clips copy` stays.

The same cross-Asset inputs could later let a character take its ramps from another (`ramps_from`), which M4 avoided with a
Project ramp table ([0166](0166-m4-ramps-match-across-characters.md)).

## What to build

Settle the details after [0164](0164-m4-claude-built-base-models-trial.md) and [0153](../m5/0153-m5-character-layer-trial.md); the
direction:

- A character can name a **base** character (`new character guard --base character.body_m`, or a `base` parameter). It uses the
  base's rigged file and clip sources, and starts with its `clip` Decisions, which it may change (0156), add to or remove.
- Its own Model is imported as usual. `rig` checks the Model's skeleton matches the base's (bone names and rest proportions,
  as `rig` already compares), so no new Mixamo trip is needed. A mismatch is a finding that says which bones differ.
- A change to the base's rig or clip sources makes each character made from it stale, as any input does.
- The files aren't copied: the base's are referenced by hash, so the art repo's LFS holds them once.

## From the generator trial (2026-11-14, [0164](0164-m4-claude-built-base-models-trial.md))

Six NPCs were made on mc03's two rigs by a generator in the art repo (`urban-mystery-club-art/chargen/`). What it changes
here:

- **The skeleton check must compare bone names and hierarchy, not rest proportions.** The generator changes the rest pose
  on purpose (bone lengths for build, age and height; a stoop and bent knees for posture) and the base's clips still play,
  because a clip's rotations are relative to rest. A character from a base differs from it in exactly "rest proportions".
- **A Model with its own armature needs no rigged file:** the generator's GLB carries the base's skeleton, `rig`
  validates it, and `clips copy` brought mc03's clips. So today's cost of no base is only the copy: 5 to 6 MB of clip sources
  in each NPC's `src/clips/` (the same three files, copied into each of the six NPCs), and Stage parameters set by hand on each
  (`render` bands, shadow and eyes; `finish` outline colour and eyes). A base should give both.
- **Height:** each NPC's `render` `height` was set from its Model's height against the base's (47 to 56 px against 52).
  With a base, `render` could do that itself: the base's px height times the ratio of the two Models' heights.
- **Time to a new NPC from a base, measured:** 75 to 98 s of Kiripix (model to export, 3 clips, 8 directions), no Owner
  time and no Mixamo trip, against mc02's 16 minutes of Mixamo alone.

## Settled, 2026-11-14

- **No need to wait for the layer trial [0153](../m5/0153-m5-character-layer-trial.md).** The generator trial answered
  what a base needs (above). 0153 answers how a layer is held (0152's question 3), which a base doesn't need.
- **`clips copy` stays** (the Owner), for characters that share clips but not a body.
- **The design is [ADR 0012](../../docs/adr/0012-a-character-can-be-made-from-a-base.md)** (proposed; the Owner reviews it
  before code). In short: `base` is an Asset parameter; a Stage declares what it reads of the base (`StageInputs.base`:
  files, Decisions, built Stages), and core hashes it; parameters fall back to the base's; the base's clips come first and
  the character's own Decisions add, replace or `remove`; `rig` compares bone names and hierarchy; `render` `height`
  follows the two Models' heights. It replaces "uses the base's rigged file" above: the character's Model carries the
  skeleton.
- **Done in the main session** (the Owner), the core part included, though it spans `core-engineer`'s area.

## Built, 2026-11-14

In the main session. Tests: `tests/cli/test_character_base.py` (19, on the fake Blender). The design as built is in
[ADR 0012](../../docs/adr/0012-a-character-can-be-made-from-a-base.md) (accepted) and spec §6.3.

- **What building it changed in the ADR:** the height ratio is between the two rigs' files, not the two Models'. On mc03
  the Model file is 1.78 units tall and the rigged file from Mixamo 2.0, and an NPC is built from the rigged file, so
  against the Model an NPC came out at 56 px of 52, and against the rigged file at 50. `rig.json` (schema 2) records the
  height with the bones' parents. `model`'s `facing` is never taken from the base. The base's `bone` roles hold for the
  character.
- **A limit:** only clip-source files cross from the base. A base clip that plays an action of the base's own Model file
  is `clips.source_missing` on the character, and the finding says to give the base that animation as a clip source.
- **Checked on real files** (Blender 5.2, a scratch Project with copies of mc03_male and `npc_elder_coat`'s GLB; nothing
  in the art repo was changed): the base's rigged FBX and the NPC's GLB have the same 65 bones under the same parents;
  `kiripix run` on the NPC built `model` to `sheet` with the base's three clips read from the base's folder, at 50 px.
- **Time to a new NPC from a base:** 58 s of Kiripix, `model` to `sheet` (3 clips, 8 directions, GPU), with no copy of
  clips and no parameters set by hand. The trial's NPCs took 75 to 98 s, `model` to `export`, after a script had copied
  the clips and set the parameters. mc02's Mixamo round trip alone was 16 minutes. `export` was not timed here: the
  scratch Project has no game.
- **For the art repo, not done here:** make `mc03_male` and `mc03_female` the bases (`kiripix run <base> rig --force`
  once, for the new `rig.json`), add `base = "character.mc03_male"` to each NPC, and take out the NPCs' copied clips,
  `height`, `bands`, `shadow` and outline colour.
- **The UI** is [0227](0227-m4-ui-a-character-made-from-a-base.md).

## Acceptance criteria

- [x] CLI seam, on the fake: a character made from a base reaches `render` with no `rig` round trip and the base's clips; a
      clip it changes doesn't change the base's.
- [x] Unset Stage parameters take the base's; one set on the character wins. `render` `height` follows the two rigs'
      heights when unset.
- [x] A base that is missing, not a character, the Asset itself or made from a base is `asset.base_invalid`.
- [x] `clips` `remove` takes a base clip away from the character only.
- [x] A Model whose skeleton doesn't match the base fails `rig` (`rig.base_mismatch`) with the bones named.
- [x] Changing the base's clip source makes the derived character's `clips` and `render` stale.
- [x] Time to a new NPC from a base is recorded here, against mc02's.
