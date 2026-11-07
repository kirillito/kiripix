---
status: todo
milestone: M4
type: spec
---

# M4: room Looks

Background: [the spec](../docs/KIRIPIX_SPEC.md) §6.1 (Looks), §9 and §16 open decision 8; [ADR 0009](../docs/adr/0009-a-rooms-looks-are-a-stage-on-the-room.md);
[the glossary](../GLOSSARY.md) (Look, Condition). Lost-and-Found's D10 "states" are the reference (`docs/TECHNICAL.md`,
`scripts/gen/backgrounds.py` and `scripts/gen/backgrounds/hub.json` in that repo); read them, don't copy them.

## Problem Statement

A room has one Source, so it reaches the game with one look. As soon as a door shuts or a lamp goes out, the other
look has to be painted too, and Kiripix has nowhere to put it. In Lost-and-Found these looks became one of the art
pipeline's most-used parts.

## Solution

- A `looks` Stage after `palette`. Each Look has an ID, a Condition, a picked edit of the room's Source, a region and,
  optionally, its own `solid` Mask.
- An edit is resized and registered to the Source, fitted with the room's Grid transform, mapped as the room is mapped,
  and cut to its region. Its pixels over a foreground Layer go to a piece at that Layer's depth.
- Checks: on the palette, registered, drift outside the region reported, and the region shows a change.
- `room.json` schema 3 carries the Looks; Godot gets hidden `Sprite2D`s and a disabled `StaticBody2D` per Look.

## Order

1. [0119](0119-m4-room-look-edit-trial.md): trial: what an image model's edit of a ch01 room really changes. Sets the
   defaults below.
2. [0120](0120-m4-look-variants.md) (core): edit Variants, `import --look`, `pick --look`.
3. [0121](0121-m4-looks-stage.md) (imaging): the Stage, its Decisions and Checks.
4. [0122](0122-m4-looks-export.md) (export): `room.json` schema 3 and the Godot scene.
5. [0123](0123-m4-ui-looks-screen.md) (UI): the looks screen.
6. [0124](0124-m4-gen-a-look-edit.md) (Providers): `gen --look`, after M4's first Provider.

## User Stories

1. As the Owner, I want to import an edit of a room as a Look with a Condition, so that the game can show a shut door.
2. As the Owner, I want an edit that came back at another size or slightly rescaled to line up anyway, or to be told it
   doesn't, so that the picture never jumps when the Look toggles.
3. As the Owner, I want to see where the edit changed the room outside the region, so that the model's drift is never
   hidden.
4. As the Owner, I want a Look over a foreground Layer to sort with that Layer, so that the player stays in front of or
   behind it.
5. As the Owner, I want a shut door's collision to come with its Look, so that the game enables both together.
6. As the Owner, I want a new Source to stop every Look until I re-make its edit, so that an edit of the old picture is
   never cut into the new one.
7. As an agent, I want the Looks in `room.json`, so that another Exporter can read them without parsing a Godot scene.

## Out of scope

Open decision 8: stacked or combined Looks, a Look that takes collision away or changes walkable or `reach`, Markers
per Look, soft edges.
