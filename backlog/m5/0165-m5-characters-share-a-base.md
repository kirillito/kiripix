---
status: todo
milestone: M5
agent: character-pipeline
type: ticket
parent: 0152-m5-character-layers.md
depends_on: [0164-m5-claude-built-base-models-trial.md, 0153-m5-character-layer-trial.md]
---

# M5: characters made from a base share its rig and clips

Spec §6.3 (model, rig, clips). From the M3 gate ([0117](../m3/0117-m3-gate.md)): "if I figure out how to build 3D models
faster, or at least build a base collection of those models, moving forward it will get easier to build new characters."

## The gap

Each character today does the whole round trip on its own: import the Model, upload it to Mixamo, auto-rig, find and download
each animation, import the rigged file and every clip source, and decide every clip. On mc02 the Mixamo round trip alone was
16 minutes of the journal. NPCs and enemies built on the same body (with another head, hair or outfit, and the same skeleton)
repeat all of it.

## What to build

Settle the details after [0164](0164-m5-claude-built-base-models-trial.md) and [0153](0153-m5-character-layer-trial.md); the
direction:

- A character can name a **base** character (`new character guard --base character.body_m`, or a `base` parameter). It uses the
  base's rigged file and clip sources, and starts with its `clip` Decisions, which it may change (0156), add to or remove.
- Its own Model is imported as usual. `rig` checks the Model's skeleton matches the base's (bone names and rest proportions,
  as `rig` already compares), so no new Mixamo trip is needed. A mismatch is a finding that says which bones differ.
- A change to the base's rig or clip sources makes each character made from it stale, as any input does.
- The files aren't copied: the base's are referenced by hash, so the art repo's LFS holds them once.

## Acceptance criteria

- [ ] CLI seam, on the fake: a character made from a base reaches `render` with no `rig` round trip and the base's clips; a
      clip it changes doesn't change the base's.
- [ ] A Model whose skeleton doesn't match the base fails `rig` with the bones named.
- [ ] Changing the base's clip source makes the derived character's `clips` and `render` stale.
- [ ] Time to a new NPC from a base is recorded here, against mc02's.
