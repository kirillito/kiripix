---
status: todo
milestone: M5
type: spec
parent: 0236-m5-the-games-next-needs.md
---

# M5: a `portrait` Kind: a character's dialogue portraits, one per emotion

Part of [0236](0236-m5-the-games-next-needs.md), item 2. Child tickets: [0241](0241-m5-portrait-trial.md) (trial),
[0242](0242-m5-portrait-asset-and-emotions.md), [0274](0274-m5-set-colours-op.md) (the set's colours),
[0243](0243-m5-portrait-recipe.md), [0244](0244-m5-export-a-portrait.md), [0245](0245-m5-ui-portrait-screens.md).

Background: spec §3 (Kinds: `portrait` was Later), §6.1 (Looks: an edit of a Source, registered to it), §6.2 (Prop: `cutout`,
`fit`), §6.3 (`palette`, `finish`). The game's `docs/MILESTONE_PLANS.md` § M04 (M04-01 to M04-07, acceptance and risks),
`docs/TECHNICAL.md` §6 ("portrait preset"), DEC-061 and DEC-062.

## Problem Statement

The game's M04, its next milestone, shows large waist-up portraits in dialogue, and the expression changes line by line.
The canvas is about 160 x 224 px, to be confirmed by the game's M04-01.

- **The set:** each character with portraits has a neutral image plus about six emotions (neutral, happy, sad, angry,
  surprised, worried; extras per character). Only the main cast and key NPCs get portraits, not the MC.
- **How they're made:** the Owner makes the neutral image in the image model, and each emotion as an edit of it.
- **The rule:** an emotion swap must never move the body by a pixel. Image models shift and rescale an edit slightly, as
  Looks found (§6.1).

Kiripix has no Kind for this. A Prop is one image, and a Look is part of a room. The game's fallback is a script in the art
repo.

## Solution (the direction; the trial settles the open parts)

A new Kind, `portrait`. One Asset holds one character's set (`portrait.sanjay`). The emotions are not Looks and not
Variants of the Source: each is a named member of the set, with its own Variants and Pick, the way a Look has its edits.

**brief → source → cutout → register → fit → palette → finish → export**

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **brief** | The canvas (w, h), the anchor (a pixel of the canvas; bottom centre by default), the fallback emotion (`neutral`). The canvas size is a Project setting, `[portrait] canvas`, so every set matches. | Writes the brief | Canvas no larger than the Project's resolution |
| **source** | The neutral image is the Source (a Pick). An `emotion` Decision declares an ID (snake_case, unique in the set). `import <id> <png> --emotion <e>` adds a Variant of it, and `pick <id> <v> --emotion <e>` chooses one, recording the hash of the neutral Source it was made from. | Imports, names, picks | `portrait.emotion_unpicked`; an emotion picked on another neutral is needs-input, as a Look's is |
| **cutout** | Per image: chroma key or matting (BiRefNet, pinned per image), as the Prop's. | Picks the method | As the Prop's |
| **register** | Each emotion to the neutral: scale and shift over the figure, with the Looks' registration Op, outside an optional `face` region. The neutral is the reference. | Draws `face`, only if needed | `portrait.misaligned` (error, over half a target pixel after registration); residual per emotion (info) |
| **fit** | One Grid transform for the set, from the neutral: one scale and one crop onto the canvas at the anchor. Alpha by vote. | Tunes the crop | Exact canvas size |
| **palette** | **The set's own colours, not the Project palette** (the Owner, 2026-11-16, below): `n` colours chosen once over every image of the set ([0274](0274-m5-set-colours-op.md)), so a shade can't flip between emotions and gradients survive. `keep` holds colours that must be there (the outline's). `mode` is `set` (default), `project` (strict, as a Prop) or `off` (only the alpha is binarised). | `n`, dither, `keep` | Every pixel on the set's colours; the error per image (info) |
| **finish** | The outline, matching the characters' colour and width (`outline_colour`, the Project's default). Optionally `lock_outside_face`: outside the `face` region every emotion takes the neutral's pixels. | — | `portrait.shimmer` (info): per emotion, the pixels outside `face` (or anywhere, without one) that differ from the neutral's, with boxes |
| **export** | One PNG per emotion, all on one canvas with one anchor, and `portrait.json`. | — | Every image the same canvas and anchor; binary alpha |

**Export (godot-export):** `portraits/<asset>/<emotion>.png` and `portrait.json` (`schema_version`, `asset`, `canvas`,
`anchor`, `fallback`, `emotions`: ID and file). No scene: the game's portrait UI loads them. The emotion IDs are frozen once
exported, like clip names (ADR 0003).

**Measure:** `stats` per emotion (the Owner's minutes on `source` and `register`), which the game reports at its CP1.

**From M6,** `gen <id> --emotion <e>` makes an emotion through a Provider, as `gen --look` does for a Look. Not in M5.

## Open, for the trial [0241](0241-m5-portrait-trial.md)

1. **Does registration hold** on the free image model's whole-image edits of a portrait? What residual, and is a `face`
   region needed so the changed face doesn't pull the estimate?
2. **Shimmer:** after one fit and one palette mapping, how many pixels outside the face change between emotions? Does
   `lock_outside_face` need to be in the first build, or can it wait until the shimmer shows in the game?
3. ~~Skin and hair on the ramp table~~: **decided by the Owner, 2026-11-16: no.** "Only color, and only partially. I will
   generate portraits, they shouldn't depend too much on character sprites. There will be gradients at portraits that will
   definitely not match strict sprite palette requirements." So a portrait has its own colours for its set, no Ramps and no
   swap. It's an exception to principle 6 (every exported pixel a Project palette colour), recorded in spec §2. The trial
   instead finds the `n` that keeps the gradients without shimmer.
4. **The canvas and scale:** what the image model gives at 160 x 224 after `downscale`, and whether the style reads beside a
   painted room and a 52 px sprite (the game's M04-02 style test).

## Order

| Wave | Tickets |
|---|---|
| 1 | [0241](0241-m5-portrait-trial.md) the trial |
| 2 | [0274](0274-m5-set-colours-op.md) the Op (any time, no dependency), [0242](0242-m5-portrait-asset-and-emotions.md) the Kind, `emotion` and import (core), then [0243](0243-m5-portrait-recipe.md) the Stages, then [0244](0244-m5-export-a-portrait.md) export and [0245](0245-m5-ui-portrait-screens.md) the UI |

## Out of scope

- The game's portrait UI, transitions and dimming.
- A mouth or eyes stamped on a 3D character's face (0203's "Open").
- Portraits from the 3D Model: the game's portraits are painted.
