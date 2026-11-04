# Kiripix

Kiripix turns generated or imported images and 3D models into consistent, game-ready pixel art assets for one game
project, and exports them into Godot.

## Workspace

**Project**:
One game's asset workspace, with its palette, resolution, tile size, style bible, Mask definitions and export target.

**Asset**:
One thing in the game, with a Kind and a stable ID, such as `room.queen_west_alley`. Its ID is frozen once exported.
_Avoid_: item, resource

**Kind**:
An Asset's type, which fixes its Recipe: room, prop, character.
_Avoid_: type, category

**Recipe**:
A Kind's ordered list of Stages.
_Avoid_: pipeline, workflow

**Stage**:
One step of a Recipe, with declared inputs, parameters, outputs and Checks.
_Avoid_: step, task

**Stale**:
A Stage whose inputs have changed since its output was produced.

**Needs-review**:
A Stage that has produced output by replaying Decisions onto changed input, and waits for the owner to confirm it.

**Needs-input**:
A Stage that cannot produce output until the owner makes a Decision.

## Human input

**Owner**:
The one person whose Decisions and acceptances Kiripix records as human judgement. An agent is never the Owner.
_Avoid_: user (ambiguous with agents), admin

**Decision journal**:
A Stage's ordered, append-only record of Decisions, including undos and redos.

**Decision**:
Recorded human input that a Stage replays: a Pick, segmentation clicks, an Override, marker positions.

**Pick**:
The Decision choosing one Variant as an Asset's Source.

**Override**:
A recorded hand edit painted onto a Stage's image output, tied to the exact image it was painted on.
_Avoid_: layer, patch, hand edit

## Sources

**Variant**:
One candidate image or model, generated or imported, offered for a Pick.

**Source**:
The picked Variant that a Recipe builds from. Immutable once picked.

**Model**:
A 3D model that a character is rendered from.
_Avoid_: mesh (when meaning the whole character), ML model

**Provider**:
An image or model generator behind one interface, external or local.
_Avoid_: generator, API

**Runner**:
A local ML model used by a Stage, for segmentation, matting, depth or inpainting. Its files are its weights.
_Avoid_: model, ML model

**Pinned output**:
A committed result of a Runner or Provider, kept with its input hash so that a rebuild never re-runs it implicitly.

## Image structure

**Grid transform**:
The recorded scale and offset that map an Asset's Source onto its target pixel grid.

**Layer**:
A visible image plane of a room: the Plate, a foreground Layer or a parallax plane.
_Avoid_: mask (for anything visible)

**Plate**:
The room's Layer with every foreground object removed and the holes filled.
_Avoid_: background (ambiguous), base

**Mask**:
A named binary gameplay region read by the engine, such as `solid` or `ladder`.
_Avoid_: layer, collision layer

**Derived mask**:
A Mask computed from other data, never painted, such as `walkable` or `foreground`.

**Walkable**:
The Derived mask of every spot where the Body's footprint fits without touching `solid` or a Pit. It says nothing about
reachability.

**Pit**:
A painted Mask of a top-view Room that the Body can't walk on but can dash over, if its dash is at least as wide. `solid`
stops a dash; a Pit doesn't.
_Avoid_: gap (a way through `solid`, which the reach report measures)

**Reachable**:
Walkable ground the Body can get to from a Spawn or an Exit.

## Rooms

**Room**:
An Asset of Kind room: a background with Layers, Masks and Markers, in top or side view.
_Avoid_: scene, level, map, background

**Marker**:
A placed point or line on a Room with a stable ID: an Exit, a Spawn, a light, an emitter or a y-sort line.

**Exit**:
A Marker that leads to an Exit in another Room.
_Avoid_: door, portal

**Spawn**:
A Marker where an actor can enter a Room without coming through an Exit.

**Body**:
The stand-in player footprint used for reachability and walk tests.

**Y-sort line**:
The line on a foreground Layer that decides whether it is drawn over or under an actor.

## Verification and output

**Check**:
A verification with a pass/fail result and located findings.
_Avoid_: validation, test

**Project check**:
A Check across Assets, such as Exit pairing, that belongs to no single Asset's Stages.

**Command**:
One operation of Kiripix, defined once and offered identically through the CLI, the REST API and MCP. A REST-only
transport route (files, events, cancel) is not a Command (ADR 0007).
_Avoid_: endpoint, tool, action (for the operation itself)

**Probe**:
A read-only Command whose result is never recorded or pinned, such as a segmentation preview on hover.
_Avoid_: preview (that is a Command that writes a preview image)

**Op**:
A pure image function, such as quantise or flood fill.
_Avoid_: function, filter, tool

**Exporter**:
The part that writes engine files from an Asset's final outputs.

**Manifest**:
The record of every file Kiripix has exported, with its hash, which decides what Kiripix may overwrite.
