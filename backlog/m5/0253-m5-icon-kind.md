---
status: todo
milestone: M5
type: spec
parent: 0236-m5-the-games-next-needs.md
---

# M5: an `icon` Kind: item and skill icons at a fixed square size

Spec §3 (Kinds), §6.2 (Prop), §14 Later ("UI icons"). Part of [0236](0236-m5-the-games-next-needs.md), item 10. The game's
`docs/MILESTONE_PLANS.md` M08-03 to M08-05: item icons for the inventory, the "item get" moment, collectibles and the
collection journal; later, skill icons for the battle menu.

## Problem Statement

An icon is the front half of a Prop: a source, a cutout, a fit, the palette and an outline. It has no footprint and no
origin, and it lands on a fixed square (16, 24 or 32 px) instead of a brief's size. Today the game would make icons as Props
and ignore their collision. Or it would fit them by hand, and miss the palette Check.

## Solution (the direction)

**brief → source → cutout → fit → palette → finish → export**

- **brief:** `size` (16, 24 or 32; a Project default `[icon] size`), a `padding` in px, notes.
- **source, cutout, palette, finish:** the Prop's.
- **fit:** the Prop's `downscale` or `grid`, onto the square, centred, with the padding. The alpha goes to the grid by vote.
- **export:** `icon.png` and `icon.json` (`schema_version`, `asset`, `size`). The Exporter writes them under `icons/`.
- **Checks:** exactly the square's size, binary alpha, the palette.

## Open, to settle when it's scheduled (the game needs it at its M08)

1. **One Asset per icon, or a set** like a portrait's emotions (`icon.items` holding `phone`, `metro_pass`...)? One per icon
   is simpler, and each has its own source and cutout. A set gives one atlas. Recommended: one per icon, unless the game's
   M08 wants an atlas.
2. **An atlas across Assets** (`icons/atlas.png` and a JSON keyed by icon ID) is a Project-level export, which Kiripix
   doesn't have. Godot can atlas the PNGs itself. Ask the game first.
3. **A Kind, or a Prop with `footprint` off?** A Kind keeps `describe` honest and the brief simple. Recommended: a Kind.

## Order

Filed on the recommendations above (2026-11-16): [0262](0262-m5-icon-kind-and-stages.md) the Kind and its Stages,
[0263](0263-m5-export-an-icon.md) export, [0264](0264-m5-ui-icon-screens.md) the UI. If the game's M08 asks for an atlas,
or the Owner overturns a recommendation, update them before they start.

## Out of scope

- Animated icons, and icons drawn by hand: those import as a Source like any image.
