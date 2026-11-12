---
status: todo
milestone: M4
type: spec
---

# M4: palette ramps per part, so the game can recolour a character

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6.3 (palette), §9, §14 (M4) and §16 (open decision 9); ADR 0004 and
[0110](../m3/0110-m3-character-palette-stage.md) (the character `palette` Stage). The game's decisions are in
`../urban-mystery-club/docs/DECISION_LOG.md` (DEC-051 to DEC-054) and `docs/TECHNICAL.md` ("Player avatar", "Kiripix
requests"). The first real character is `character.mc02` in the art Project (`urban-mystery-club-art`).

## Problem Statement

The game's MC is customisable (DEC-027, DEC-052): skin, hair and each clothing piece are recoloured by a palette-swap shader in
the game, with no extra render. A swap of one part's colours must touch no other pixel, so each part needs colours of its own.

Today the character `palette` Stage picks one subset of the Project palette (`colors`, 16 by default) across every frame, by
OKLab fit. Parts share colours. On mc02 the hair (0.11, 0.05, 0.03) and the boots (0.12, 0.05, 0.03) are nearly the same
colour, and the dark greys of the jacket, hood and backpack draw on the same few palette colours, so swapping the hair would
recolour the boots.

## Solution

The Owner decided on 2026-11-11:

- **A part is a Blender material.** mc02 already has one material per part (skin, jacket, jeans, boots, eyes, hair, hood,
  backpack, straps), and Mixamo's round trip keeps the names (checked on mc02's rigged file). `render` writes a material-index
  pass, so every pixel knows its material.
- **Each swappable part owns a ramp**: its own palette colours, in order from dark to light, which no other part, fixed colour or
  the outline uses. The `palette` Stage's `parts` parameter names the swappable parts; a part may group several materials
  (`jacket+hood`). Materials not named are fixed: they share one subset as today, but never a ramp's colour. With no `parts`,
  the Stage behaves as it does now.
- **A ramp's length** defaults to the toon `bands` (3), since a flat material renders as exactly that many colours; a textured
  part may need more, set per part.
- **The export gives the game both:** `parts` in `character.json` (each part's name, materials, palette indexes and RGB, dark to
  light) and a `ramps.png` beside the atlases, one row per part, for the swap shader.
- **It comes first in M4,** before the rooms work. A character rendered before the rule only rebuilds, from `render` down (about
  2 minutes for mc02), so nothing made in M3 is lost. The game needs it for its M03-05 swap shader.

## Checked, no work needed (2026-11-11)

- **Camera (the game's DEC-054):** `top34_8` (30°, 8 directions) is `render`'s default `camera` and is in every new Project's
  `[character.camera.top34_8]`. For a PixelLab `init_image`, the `model` Stage's `work/model/still.png` is a 256 px front view at
  the same 30°; a one-frame clip (start = end) renders a 52 px frame in every direction in about a second.
- **Class battle-clip sets (the game's DEC-051):** one character holds every class's clips, named by the game's convention, such
  as `attack_melee` (lower-case snake_case, not ending in a direction). Kiripix has no notion of a clip set. Every clip of a
  character goes into one atlas, so all three classes' battle frames are one texture. If the game wants a texture per class,
  each class can instead be its own character Asset made from the same Model, which renders the shared exploration clips once
  per class.

## Order

| Wave | Tickets |
|---|---|
| 1 | [0148](0148-m4-render-material-pass.md) and [0149](0149-m4-part-ramp-ops.md), side by side |
| 2 | [0150](0150-m4-palette-ramps-per-part.md) |
| 3 | [0151](0151-m4-export-part-ramps.md) |

Then mc02: set `parts`, rebuild, export, and check in Godot that a test shader swapping the skin ramp changes no other pixel
(the M4 gate, [0142](0142-m4-gate.md)).

**Don't run 0150 alongside 0148:** both edit the character recipe's `render.json` contract.

## User Stories

1. As the game, I want each swappable part's colours to be its own, so that recolouring the hair never changes the boots.
2. As the game, I want each part's ramp as data and as a texture, so that the swap shader needs no Kiripix knowledge.
3. As the Owner, I want parts to be the materials I already have, so that a Model needs no extra setup and survives Mixamo.
4. As the Owner, I want a Check that fails when two parts share a colour, so that a bad swap is caught before export.

## Out of scope

- The same parts, lengths, rows and (for skin and hair) colours on every character, which the game's four M03 bodies need: a
  spec of its own after these tickets, [0166](0166-m4-ramps-match-across-characters.md). 0150 and 0151 should key everything by
  part name, not position, so that 0166 only adds a Project order.
- Per-part layer renders (hair styles and outfits as layers): M5, [0152](../m5/0152-m5-character-layers.md).
- The game's swap shader and appearance data.
- A palette screen showing the ramps in the UI. A follow-up, if the Owner wants it.
