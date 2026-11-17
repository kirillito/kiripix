---
status: todo
milestone: M5
type: spec
parent: 0236-m5-the-games-next-needs.md
---

# M5: a Prop's states: a bin standing, toppled, dented...

Spec §6.2 (Prop) and §9 (Prop). Part of [0236](0236-m5-the-games-next-needs.md), item 3. Child tickets:
[0258](0258-m5-prop-state-decision-and-import.md), [0259](0259-m5-prop-stages-per-state.md),
[0260](0260-m5-export-prop-states.md), [0261](0261-m5-ui-prop-states.md).

The game's `docs/MILESTONE_PLANS.md` M05-02, M05-08 and M06-07, and `docs/TECHNICAL.md` ("Movable battle objects (bins) are
Kiripix Props"). Asked for by the Owner on 2026-11-16: "There might be more than two, why not support several?"

## Problem Statement

The laneway's green bins are Props the game places, and in the boss fight they get knocked over (M06-07). A toppled bin is
another sprite, with another footprint and its own origin. More objects will have more than two states (a crate whole,
cracked and broken; a door shut and open). Two separate Prop Assets per object works, but then:

- nothing ties the states together;
- their scale can drift apart;
- the game keeps the pairing in its own data.

## Solution

One Prop holds its states. The picked Source is the **default state**. Each other state has its own image (often an
image-model edit of the default, but it needn't line up with it), its own cutout, size, footprint and origin, and shares the
Prop's scale, palette and `finish`.

| Stage | With states |
|---|---|
| **brief** | The default state's ID (`state`, default `default`) and size. Each other state's size is in its `state` Decision. |
| **source** | A `state` Decision declares an ID (snake_case, unique in the Prop) and its size. `import <id> <png> --state <s>` adds a Variant of that state, and `pick <id> <v> --state <s>` chooses it. A new default Source doesn't invalidate the other states: they aren't edits of it. |
| **cutout** | Per state, with its own Decisions (each names its state). |
| **fit** | Per state, with **one scale for the Prop**, the default's, so every state has the same pixel density. Each state has its own crop and offset. `fit.scale_differs` is an error if a state's `grid` scale differs. |
| **palette**, **finish** | Per state, with the Prop's parameters. |
| **footprint** | Per state: its own polygon and origin. Every state needs an origin (`footprint.no_origin`, naming the state). An empty footprint is allowed, as now (a flattened box you can walk over). |
| **export** | One scene: a `Node2D` root, and one `Node2D` per state named by its ID, each with its `Sprite2D` and `StaticBody2D`. Only the default is `visible`; the others are hidden with their polygons `disabled = true`. Metadata `kiripix_id`, `kiripix_type = "prop_state"`, `kiripix_state`. `prop.json` gets `states` (ID, file, size, origin, collision) and `default`. State IDs are frozen once exported. |

The game switches a state by showing that node and enabling its polygons, as it does a Look. A Prop with no `state`
Decision is exported exactly as now: no state nodes, and `prop.json` is unchanged but for its `schema_version`.

## Out of scope

- Frames between states (the bin falling): animation authoring is out (spec §1). The game tweens.
- A state that's a Loop (a flickering sign): a frame Loop is a room's. "A Prop with frames" stays out (0183).
