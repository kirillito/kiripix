---
status: todo
milestone: M5
type: spec
---

# M5: hair styles and outfits as layers over a character

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6.3, §14 (M5) and §16 (open decision 9). The game's decisions are in
`../urban-mystery-club/docs/DECISION_LOG.md` (DEC-013, DEC-052) and `docs/TECHNICAL.md` ("Player avatar"). Builds on M4's
palette ramps per part ([0147](../m4/0147-m4-character-palette-ramps.md)).

## Problem Statement

The game's MC is customisable: 2 bodies (one per gender), each with shared exploration clips and 3 battle-clip sets (one per
class), and a choice of hair styles and outfits. Until this milestone, an outfit is a whole-body variant, rendered in full. Every
combination of hair and outfit rendered in full would multiply: a full body with about 15 clips is about 10 minutes of rendering
(mc02: about 70 ms a frame at 52 px, plus `palette` and `finish`).

The game's M10 needs hair styles and outfits as **layers**: each rendered once, stacked on the body in the game, so the cost
adds per layer and no combination is ever rendered.

## Solution (the direction; the trial settles the rest)

- A layer (a hair style, an outfit, or one piece of it) is rendered with **the body as a holdout**: the body hides what's behind
  it but isn't drawn, so the layer holds only the pixels that show. Same clips (battle clips included), camera, frames, cell and
  pivot as the body, so the game stacks them pixel for pixel.
- A layer's parts keep their own palette ramps, disjoint from the body's (M4's rule), so a recoloured layer touches nothing else.
- The body under an outfit isn't rendered where the outfit always covers it, or the game draws it and the outfit over it; the
  trial picks one.

Open, for the trial [0153](0153-m5-character-layer-trial.md) to settle before the work tickets are written:

1. **Outfits that change the silhouette,** such as a long coat over the legs, or a hood over the hair: does stacking in a fixed
   order hold in every direction and frame, or does a layer need a per-frame order?
2. **The outline and the normal map:** per layer in Kiripix, or once on the stacked result in the game? A per-layer outline
   draws lines between layers that a single figure wouldn't have.
3. **How Kiripix holds a layer:** a Variant of the character, its own Asset that names its body, or something else, and how its
   render stays in step with the body's when the body changes.

## Order

| Wave | Tickets |
|---|---|
| 1 | [0153](0153-m5-character-layer-trial.md), the trial, and [0164](0164-m5-claude-built-base-models-trial.md), the two base Models (male and female) built by Claude in Blender |
| 2 | The work tickets the trials file, and [0165](0165-m5-characters-share-a-base.md): characters made from a base share its rig and clips |

Needs M4 done: the game's M04 and M05 need M4 first. The game needs layers by its M10.

## Out of scope

- The game's compositor (`CharacterSprite`) and appearance data.
- Rendering combinations: never.
