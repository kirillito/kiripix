# Kiripix

Kiripix turns generated or imported images and 3D models into consistent, game-ready pixel art assets for one game
project, and exports them into Godot.

## Workspace

**Project**:
One game's asset workspace, with its palette, resolution, tile size, style bible, Mask definitions and export target.

**Asset**:
One thing in the game, with a Kind and a stable ID, such as `room.queen_west_alley`. Its ID is frozen once exported.
_Avoid_: item, resource

**District**:
The Assets whose IDs an ID glob matches, such as the rooms `room.ch01_dungeon_*`. It is a word for that set, given as `--match <glob>` on `status`, `check`, `run`, `export` and `stats`; nothing about it is stored.
_Avoid_: group, area, chapter folder

**Kind**:
An Asset's type, which fixes its Recipe: room, prop, icon, character, sprite.
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

**Hand-over note**:
A note on a Stage in an Asset's `notes.jsonl`, written with `kiripix note`: why a pass stopped and what is left. It is not
a Decision: it changes no output and no input hash, and `undo` doesn't reach it. It is live while its Stage has no newer
Decision and no `accept`; that is derived, never stored.

**Review queue**:
What `kiripix queue` lists: every stop the Owner owns across the Assets (a `needs-review` Stage, an owner-only `needs-input`,
a finding with an `owner_action`), each with its Stage's live hand-over notes. A finding with a `fix` is counted per Asset, not
listed. Derived each time, never stored.

**Decision**:
Recorded human input that a Stage replays: a Pick, segmentation clicks, an Override, marker positions.

**Pick**:
The Decision choosing one Variant as an Asset's Source. The Owner chooses between several; an agent may record it when
there is only one, which needs no judgement.

**Override**:
A recorded hand edit painted onto a Stage's image output, tied to the exact image it was painted on.
_Avoid_: layer, patch, hand edit

## Sources

**Variant**:
One candidate image or model, generated or imported, offered for a Pick: of an Asset's Source, or of a Look's edit.

**Source**:
The picked Variant that a Recipe builds from. Immutable once picked. A generated character's Source is its parameter
file, which needs no Pick.

**Model**:
A 3D model that a character is rendered from.
_Avoid_: mesh (when meaning the whole character), ML model

**Base character**:
The character another character is made from, named by `base` in its `asset.toml` (ADR 0012). The character's Model
carries the base's skeleton, it starts with the base's clips and clip sources, and a Stage parameter it doesn't set
takes the base's value. A base has no base of its own. Not a room's Base.
_Avoid_: parent, template, body (the game's word for the two MC bodies)

**Generator**:
A script of the Project's own that builds a Model from a parameter file, run in the Project's Blender and named under
`[character.generators]` in `kiripix.toml`. Kiripix runs it and reads what it wrote; it holds no parts of its own. Not
a Provider.

**Parameter file**:
The file a generator builds one character's Model from (its base body, shape, parts and colours, in the generator's own
words), kept in the character's `src/parameters/`. It may be edited in place: a change makes `model` stale.

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

**Normal map**:
An image beside an Asset's colour image that gives each pixel's surface direction, so Godot's 2D lights can shade it. A
character's comes from its render; a room's comes from its `normals` Stage, out of a depth Runner (ADR 0014).
It is never palette-mapped. Flat means facing the camera.
_Avoid_: bump map, height map, depth map (the depth Runner's output, which the Stage turns into normals)

**Layer**:
A visible image plane of a room: the Plate, a foreground Layer or a parallax plane.
_Avoid_: mask (for anything visible)

**Plate**:
The room's Layer with every foreground object removed and the holes filled.
_Avoid_: background (ambiguous), base

**Mask**:
A named binary gameplay region read by the engine, such as `solid` or `ladder`.
Only `solid` and `pit` block anything in Kiripix. A Mask the Project names itself (`masks-add`, such as `cover` or `water`)
has no meaning in Kiripix, as an area has none: `reach` and the walk test ignore it, and the game reads it.
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

**Clear**:
The Derived mask of every spot where the Body's footprint touches no `solid`: where a dash may pass, over a Pit or not.

**Reachable**:
Walkable ground the Body can get to from a Spawn or an Exit.

## Rooms

**Room**:
An Asset of Kind room: a background with Layers, Masks and Markers, in top or side view.
_Avoid_: scene, level, map, background

**Marker**:
A placed point, line or box on a Room with a stable ID: an Exit, a Spawn, a light, an emitter, a y-sort line or an Area.

**Area**:
A Marker that is a box on a Room, optionally snapped to a cell grid. Kiripix gives it no meaning; the game decides what it
is for, such as a battle area, an escape route or an Exit's trigger box.
_Avoid_: region (that is a Look's), zone, battle area (in Kiripix's own code and messages)

**Link**:
A Marker with two ends on one Room, where an actor crosses by a scripted move (a hop, a climb, a jump).
_Avoid_: portal, traversal, jump point (and Exit, which leads to another Room)

**Exit**:
A Marker that leads to an Exit in another Room.
_Avoid_: door, portal

**Spawn**:
A Marker where an actor can enter a Room without coming through an Exit.

**Body**:
The stand-in player footprint used for reachability and walk tests.

**Y-sort line**:
The line on a foreground Layer that decides whether it is drawn over or under an actor.

**Look**:
Another appearance of part of a Room, such as a door shut, a lamp unlit or a station unbuilt. It is painted as an edit
of the room's Source, cut to a region, and shown by the game, which finds it by its ID.
_Avoid_: state (that is the game's, and Stage status is "status"), variant, overlay, patch

**State**:
Another form of a Prop, such as a bin toppled or a crate cracked. The picked Source is the default state; every other
state has its own declared ID and size, its own image, cutout, footprint and origin, and shares the Prop's scale, palette
and finish. The game shows one state at a time. Not a Stage's status, and not a Look.
_Avoid_: Look (that is a room's), variant (an image to pick from), frame, pose

**Portrait**:
A character's dialogue portraits: one Asset holds one character's set, a neutral image and an Emotion for each mood, all
on one canvas with one anchor so a swap never moves the body. The picked Source is the neutral image. The set has its own
colours, not the Project palette's.
_Avoid_: avatar, face, headshot

**Emotion**:
A named member of a Portrait set other than the neutral one, such as `happy` or `worried`: an edit of the neutral image
with its own Variants and Pick, which records the neutral Source it was made on, so a new neutral Source puts it in
needs-input. Its ID is its name in the game, frozen at its first export. Not a Look (a room's), not a State (a Prop's),
and not a Variant.
_Avoid_: expression, mood, state, look

**Condition**:
An optional label naming the game state that shows a Look, such as `circuit.hall:off`, for people and other Exporters.
Kiripix stores and exports it, and never interprets it; the game binds a Look by its ID, not by its Condition.
_Avoid_: when, flag, trigger

**Loop**:
A part of a Room that plays by itself, over and over, cut to a region: a colour cycle (chosen palette colours stepping
through a list) or frames. Its first frame is the room's own pixels, and its timing is in whole game ticks. A character
clip's `loop` flag (whether a clip repeats) is not a Loop.
_Avoid_: animation, ambient, effect, look (a Look is shown by game state; a Loop always plays)

**Base**:
The image a piece joins: a Room's Source, or the canvas so far. Not the Plate. The character a character is made from is
a Base character.

**Piece**:
An image an image model painted from a base's edge, to extend the Room past it. It overlaps the base and is joined to it.
_Avoid_: patch, tile, extension

**Overlap**:
Where a piece lies on a base: a side (`east`, `west`, `north` or `south`), how many px of the base's edge it covers, and an
offset along the edge. Written `side:width[:offset]`; a corner piece has two.

**Join**:
Putting a piece on a base in three Ops: `register-piece` (undo its rescale and shift), `match-tone` (remove a brightness
step) and `seam-join` (cut along the least difference, blended). A corner piece is seamed once per Overlap.
_Avoid_: stitch, merge, blend (a blend is only the seam's width)

## Characters

**Part**:
A swappable piece of a character's look, such as skin or hair: one or more of its Model's materials, which the `palette`
Stage gives a Ramp of its own so the game can recolour it.
_Avoid_: material (a Part may have several), layer (M5's character layers)

**Ramp**:
A Part's palette colours, dark to light, that nothing else on the character uses (not another Part, a fixed colour or the
outline). It is one row of the character's `ramps.png`.
_Avoid_: palette (the Project's), swatch

**Ramp table**:
The Project's ordered list of Parts (`[[character.ramps]]` in `kiripix.toml`, filled by `ramps-add`). It fixes each Part's
name, Ramp length and `ramps.png` row on every character, and optionally its colours, so one swap means the same on every
body.

**Clip table**:
The Project's list of clips (`[[character.clips]]` in `kiripix.toml`, filled by `clips-add`). Each row fixes a clip's rendered
frame count, fps and loop, and optionally that it has foot frames, so every body plays the same timing. A character or sprite
with a clip of that name must match (`clips.timing_differs`; a sprite only gets a warning); one without the clip is not asked.

## Sprites

**Sprite**:
An Asset of Kind sprite: an actor built from imported 2D frames, exported as a character is.
_Avoid_: sprite for one frame (say frame), or for Godot's `Sprite2D`

**Wearable**:
An Asset of Kind wearable: a hair style, an outfit, an accessory or a held thing, rendered over the character it names as
its body, with the body as a holdout, so the game stacks it on the body pixel for pixel. Not a combination: each renders once.
_Avoid_: layer (a room's image plane), outfit or costume for the Kind

**NPC**:
An Asset of Kind npc: a background figure that is a choice, not a render: a base character, Wearables rendered on that base in
a stacking order, and a named colour choice per Part. The game draws it from the base's and the Wearables' exports (ADR 0015).
Speaking characters are characters of their own, not NPCs.
_Avoid_: NPC for any non-player character with its own Model or portraits (say character)

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

**Snapshot**:
A copy of a character's or sprite's built sheet under a label (`kiripix snapshot`), with the parameters it was taken with, kept
in `.kiripix/snapshots/` so `cast-sheet --snapshots` can lay settings side by side. It records nothing in the Project.
_Avoid_: version, backup, pin (a pinned result is a Runner's, and it is an input)

**Op**:
A pure image function, such as quantise or flood fill.
_Avoid_: function, filter, tool

**Exporter**:
The part that writes engine files from an Asset's final outputs.

**Manifest**:
The record of every file Kiripix has exported, with its hash, which decides what Kiripix may overwrite.
