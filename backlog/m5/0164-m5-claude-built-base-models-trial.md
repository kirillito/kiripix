---
status: todo
milestone: M5
agent: character-pipeline
type: trial
parent: 0152-m5-character-layers.md
---

# M5: trial: base Models built by Claude in Blender

Spec §6.3 (model) and §16 (open decision 4, image-to-3D). Asked for at the M3 gate ([0117](../m3/0117-m3-gate.md)),
2026-11-11.

## Background

mc02 was built by a scripted Blender session: Claude, headless, reshaping a Quaternius base and modelling the clothes.
At the gate the Owner found Fable 5.2 "much better than expected" at this, better than Opus, and wants to make it part of
making a character, at least for one with many animations. Of the 120 minutes the Owner spent on mc02, most went into getting
and choosing a Model and the Mixamo round trip, not into Kiripix.

The game's customisable MC needs two bodies, one per gender ([0152](0152-m5-character-layers.md)), with hair styles and
outfits as layers over them. So the base Models should be bodies in underwear only, with anime-style eyes large enough to
survive 52 px (Sea of Stars, Chrono Trigger), and nothing a layer will cover.

## What to do

1. With Fable, build a **male and a female base Model** in headless Blender: underwear only, large eyes, a material per part
   (skin, eyes, hair, underwear), so M4's ramps per part ([0147](../m4/0147-m4-character-palette-ramps.md)) and M5's layers
   work. Keep each session's script with the Model, so it can be run again or revised.
2. Take each through Mixamo's auto-rig and Kiripix to export with mc02's clips, and look at it in Godot beside mc02.
3. Check what the layers trial ([0153](0153-m5-character-layer-trial.md)) needs from a base, such as clean shoulders and
   hairline for hair and outfits to sit on, and whether one session can also build a hair style or an outfit as its own
   mesh on the same skeleton.

## What to record, in this ticket

- Time per base Model: prompting, the sessions, review, Mixamo, Kiripix. Tokens if the session reports them.
- What went wrong and how often (a broken rig, wrong proportions, eyes that vanish: [0159](../m4/0159-m4-part-vanishes-check.md)).
- Where the scripts and Models live, and whether Kiripix should keep the script as a source file of the Model.
- The Owner's choice: this as the way to make bodies, and whether Kiripix needs anything for it (a ticket for each).

## Acceptance criteria

- [ ] Two base Models, rigged and rendered, their paths listed here, with the numbers above.
- [ ] The Owner's choice recorded.
