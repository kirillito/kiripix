---
status: done
milestone: M5
type: spec
parent: 0236-m5-the-games-next-needs.md
---

# M5: a `portrait` Kind: a character's dialogue portraits, one per emotion

Part of [0236](0236-m5-the-games-next-needs.md), item 2. Child tickets: [0241](0241-m5-portrait-trial.md) (trial),
[0242](0242-m5-portrait-asset-and-emotions.md), [0274](0274-m5-set-colours-op.md) (the set's colours),
[0243](0243-m5-portrait-recipe.md), [0244](0244-m5-export-a-portrait.md), [0245](0245-m5-ui-portrait-screens.md); after the
redesign, [0321](0321-m5-portrait-whole-body-emotions.md), [0322](0322-m5-portrait-light-rim-check.md) and
[0323](0323-m5-portrait-canvas-default.md).

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

## Answers (the Owner, 2026-11-18, from the trial 0241): WITHDRAWN

> Withdrawn the same day, after the Owner saw the sheets ([0241](0241-m5-portrait-trial.md), "The Owner's view"). The
> portraits are for emotion through the whole body (posture, gesture, the head's turn), not a face patch on a still body, so
> the body is expected to change between emotions, and "an emotion swap never moves the body", registration outside a
> `face` region and `lock_outside_face` are in question, and so is the half-figure crop. This Kind needs a redesign before
> 0243–0245 are built. Kept below as what was answered, for the redesign to start from. The canvas, the set's own colours
> (more of them, eventually) and one scale for a set may stand.

1. **Registration** holds on the image model's edits without a `face` region (Sanjay's set: 0.03-0.09 source px). `register`
   and `portrait.misaligned` stay, for the edits that do drift.
2. **Shimmer:** `lock_outside_face` is in the first build, on by default when a `face` region is drawn (the image model
   redraws the clothes' shading lines on every edit: 1,000-1,300 px an emotion outside the face, 0 with the lock).
3. **Colours:** the set's own, one set over every emotion, no dither. **The Owner wants more colours, at least eventually:**
   `n` is a parameter with room to grow (up to 256), its default 32 for now (the trial: 24 the least that reads smoothly, 32
   smooth). No ramps.
4. **Canvas:** 160 x 224, bottom centre, one scale from the neutral (`Grid.cover`) and one crop for the set.

## Input from the game (0091, the Owner's OK, 2026-11-19): the rules for the redesign

The game's portrait spec (its ticket 0091 and DEC-071) settles what the redesign builds for. In short:

- **Canvas 192 x 240** for the whole cast (was 160 x 224), anchor bottom centre `(96, 239)`, the figure cut at the waist on
  the bottom edge in every emotion (the game hides the bottom 8 px behind its text box).
- **Holds across a set:** one scale, from the neutral (the head the same size in every emotion); the anchor and the waist
  cut; the neutral's head top about 40 px below the canvas top; every gesture inside the canvas with 2 px to spare; the
  1 px outline in the characters' colour; the set's own colours, `n` 32, no dither, one set over every emotion; the same
  outfit, hair, colours and light; no background, no white rim.
- **Free between emotions:** the pose, the shoulders, the arms and hands, the torso's lean, the head's turn and tilt, the
  face. So `register` outside a `face` region and `lock_outside_face` don't apply; one fit for the set from the neutral
  still does. Shimmer is judged by eye, not locked.
- **Facing:** each set is drawn facing the screen's centre from its side; the game may mirror it at runtime.
- **Emotion IDs** (snake_case, frozen once exported): `neutral`, `happy`, `sad`, `angry`, `surprised`, `worried`; Sanjay
  adds `exasperated`, `smirk`, `tired`, `relieved` and optionally `proud`. `fallback` stays `neutral`.
- The export shape (0244) is unchanged.

**Recorded in [0241](0241-m5-portrait-trial.md) ("Answers after the redesign", 2026-11-19)** as the answers to the four
questions. 0242–0245 were built on the withdrawn answers, so what changes is filed: [0321](0321-m5-portrait-whole-body-emotions.md)
(`register` opt-in, `lock_outside_face` off, the fit's head top, `portrait.out_of_canvas`),
[0322](0322-m5-portrait-light-rim-check.md) (the leftover white rim) and [0323](0323-m5-portrait-canvas-default.md) (the
canvas default).

## Order

| Wave | Tickets |
|---|---|
| 1 | [0241](0241-m5-portrait-trial.md) the trial |
| 2 | [0274](0274-m5-set-colours-op.md) the Op (any time, no dependency), [0242](0242-m5-portrait-asset-and-emotions.md) the Kind, `emotion` and import (core), then [0243](0243-m5-portrait-recipe.md) the Stages, then [0244](0244-m5-export-a-portrait.md) export and [0245](0245-m5-ui-portrait-screens.md) the UI |
| 3 | The redesign: [0321](0321-m5-portrait-whole-body-emotions.md) the Stages, [0322](0322-m5-portrait-light-rim-check.md) the rim, [0323](0323-m5-portrait-canvas-default.md) the canvas (no dependency between them) |

## Out of scope

- The game's portrait UI, transitions and dimming.
- A mouth or eyes stamped on a 3D character's face (0203's "Open").
- Portraits from the 3D Model: the game's portraits are painted.

## Result

Closed by the Owner, 2026-11-19. Built in [0242](0242-m5-portrait-asset-and-emotions.md) to
[0245](0245-m5-ui-portrait-screens.md) and redesigned to the game's rules by [0321](0321-m5-portrait-whole-body-emotions.md)
(whole-body emotions, `head_top`, `portrait.out_of_canvas`), [0322](0322-m5-portrait-light-rim-check.md) (the white rim's
specks) and [0323](0323-m5-portrait-canvas-default.md) (192 x 240). Sanjay's set went from import to the game at the gate.
