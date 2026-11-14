---
status: todo
milestone: M4
type: spec
---

# M4: rooms that move: ambient animation

**Milestone: M4, every route below** (the Owner, 2026-11-12). Trial first: [0184](0184-m4-ambient-animation-trial.md).
The child tickets are under "Order". They were written before the trial, so each default the trial decides is marked
"set by 0184". The Owner's answers are under "Decisions", at the end. An ADR for the `loops` Stage (beside ADR 0009) is
drafted with 0189.

## Order

1. [0184](0184-m4-ambient-animation-trial.md) (trial, no code): the kitchen, one cycle and one frame Loop. It sets the
   defaults marked "set by 0184", and may reorder (b) and (c) or cut 0193's and 0194's Part B (edit frames).
2. Route (a), independent of the trial, any time after the area tickets:
   [0185](0185-m4-emitter-shape-direction-colours.md) (core), [0186](0186-m4-export-emitter-shape.md) (export),
   [0187](0187-m4-ui-draw-an-emitter.md) (UI).
3. Route (b), after the Looks tickets: [0188](0188-m4-cycle-ops.md) (imaging: cycle Ops),
   [0189](0189-m4-loops-stage.md) (imaging: the Stage), [0190](0190-m4-export-loops.md) (export),
   [0191](0191-m4-ui-loops-screen.md) (UI).
4. Route (c), on (b): [0192](0192-m4-frame-ops.md) (imaging: frame Ops), [0193](0193-m4-loop-kit-and-import.md) (core: kit
   and import), [0194](0194-m4-loops-build-imported-frames.md) (imaging: building imported frames),
   [0195](0195-m4-export-layer-loops.md) (export), [0196](0196-m4-ui-frame-loops.md) (UI).
5. Follow-ups found while building (b) and (c), 2026-11-13: [0204](0204-m4-palette-command.md),
   [0206](0206-m4-loops-hold-one-loop.md), [0207](0207-m4-rename-and-remove-a-loop.md),
   [0208](0208-m4-import-several-frames-over-rest.md), [0210](0210-m4-ui-loops-screen-follow-ups.md),
   [0211](0211-m4-export-layer-remainder.md), and the ADR, [0212](0212-m4-adr-the-loops-stage.md). Part B is carried by
   0184's last criterion.

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6.1 (`layers`, `masks`, `palette`, `place`, Looks), §9 (room export,
`room.json`), §16 open decision 8; [ADR 0009](../../docs/adr/0009-a-rooms-looks-are-a-stage-on-the-room.md);
[0127](../m4/0127-m4-room-looks.md) (Looks), [0174](../m4/0174-m4-sprite-kind.md) (the `sprite` Kind). The game's side:
`../urban-mystery-club/CLAUDE.md` "Non-negotiables", `docs/TECHNICAL.md` §3 (Option A, DEC-018) and §4.6 (room data,
`emitters`), `game/world/fx/dust_motes.gd` (today's only particle kind).

## Problem Statement

A Kiripix room reaches the game as one still painting. The Owner finds the game's rooms dead: the kitchen should have a
steaming cup of coffee, and later rooms want a flickering fluorescent tube or neon sign, a TV's glow, a dripping tap, rain
running down a window, a curtain or a plant swaying, a ceiling fan, a clock, an arrivals board and water shimmering in a
puddle.

The game's rules constrain how any of this can work:
- **Option A:** the Plate is never darkened or re-lit; lights reach actors only.
- **Pixel-perfect:** whole pixels, nearest filtering, binary alpha. The game screenshot-tests that the Plate is
  pixel-identical to Kiripix's composite.
- **Determinism:** animation advances from the game's frame counter in `_physics_process`, with seeded RNGs, so replays and
  captures are exact. Kiripix gives data and frames, and the game plays them.
- **$0 and the Owner's time:** no Provider until M6, so the Owner makes images in the image model's own UI. The Owner's time
  is the scarcest resource, so a route that needs no images beats one that needs good ones.

Kiripix has emitter Markers (M1), which the game fills with its own particles, and Looks (M4), edits of the Source that are
registered, fitted, mapped and cut to a region, with a piece per foreground Layer. It has nothing that changes over time.

## The five routes

| Route | What it is | Who animates | Kiripix work |
|---|---|---|---|
| **(a) Particles** | The game's particles at an emitter Marker | The game, from its own seeded code | Small: a shape, a direction and a colour list on the emitter |
| **(b) Colour cycle** | Chosen palette colours step through a cycle inside a region | Kiripix bakes the frames; the game steps through them | A new Stage, an Op, an export, a UI screen |
| **(c) Frame loop** | N frames of a part of the room, played in a loop | Kiripix builds the frames from an Op, a hand-painted kit or image-model edits; the game steps through them | (b)'s Stage, export and player, plus frame sources and Checks |
| **(d) Animated actor** | A separate object with its own frames, placed by the game | The game, as it plays a character | None: the `sprite` Kind (0174) covers it |
| **(e) Shader on the Plate** | Sway, shimmer or scroll by a runtime shader on a masked part of the Plate | The game's GPU | None; not recommended (see below) |

**Each example, and the route it takes:**

| Example | Route | Why |
|---|---|---|
| Steaming cup of coffee (kitchen) | (a) | Steam is soft, random and rises: particles at an emitter on the painted cup, going up. The cup doesn't move, so it stays painted. |
| Dripping tap | (a) | One drop falling on a line to the sink, then a splash: an emitter with a direction whose end is where the drop lands. |
| Rain running down a window | (a), or (c) by `scroll` | Drops sliding inside the glass's shape (the game has `ui/rain_overlay.gd` already). If particles look wrong on the glass, (c) with the `scroll` Op. |
| Dust in a beam, rain splashes | (a) | Already the game's kind (dust), or new particle kinds in the game. |
| Flickering fluorescent tube | (b) | The tube's own pixels step bright, dim and off in a seeded pattern. The light on actors flickers on the same pattern (the game's `PointLight2D`). |
| Neon sign | (b) | A chase along the letters (rotate) or a flicker (pulse). Classic colour cycling. |
| TV's glow | (b), or (c) | The screen's pixels cycle. The room around it is not re-lit (Option A); actors get a flickering light. Recognisable images on the screen are (c). |
| Water shimmering in a puddle | (b), or (c) by `shimmer` | The highlight colours rotate, or rows shift by a pixel. The trial picks. |
| Curtain or plant swaying | (c) by `sway` | The object becomes a foreground Layer (it may be one already); the `sway` Op shears it by whole pixels from its anchor, and the Plate's fill shows where it moved away. |
| Ceiling fan | (c) by kit | 3 or 4 frames painted by hand at target size. An image model can't turn blades consistently, and no Op foreshortens a turn. |
| Clock | (c) by kit | A pendulum or a hand in 2 to 4 frames. A second hand at 52 px characters is too small to read. |
| Arrivals board | (b) and (c) | Blinking lights or a marquee are (b); flaps changing are 2 or 3 frames, by kit or edits (signage text is allowed, DEC-021). |
| A cat | (d) | An actor: a `sprite` Asset the game places at a Marker, lit and y-sorted as an actor. Its frames are hand-made or AI images (PixelLab's animation needs a paid plan, DEC-044). |
| A cup someone picks up | (d), not (c) | A Prop or a sprite, if the game has to move or hide it. The steam on it is still (a). |

## (a) Particles: what Kiripix adds

The game owns particles: their kind, count, seed and motion stay in its room data. Kiripix adds only what is drawn on the
room, as it does for areas (the Owner's rule for exit trigger boxes, 2026-11-12: a shape drawn on the room moves with it and is
never typed into the game's data). Today the dust's polygon is typed into `data/rooms/room.annex.bedroom.json`.

The emitter Marker gets three optional fields:
- **`shape`:** `point` (the default), `line`, `box` or `polygon`, in room pixels, drawn on `place` like an area. The game reads
  it in place of its own `polygon`.
- **`direction`:** a second point. The arrow from the Marker to it gives the direction, and its length gives the travel: a drop
  falls from the tap to the arrow's end, and steam rises about that far.
- **`colours`:** a list of palette colours, picked from the palette or sampled from the room near the Marker (steam from the
  cup's lightest colours), so the particles stay on the palette.

The Godot node keeps its place and its `metadata/emitter`, and gains `metadata/shape` (`PackedVector2Array`, relative to the
node), `metadata/direction` (`Vector2`, relative) and `metadata/colours` (`PackedColorArray`). `room.json` carries the same.
Checks: `place.emitter_colour_off_palette` (error), `place.emitter_outside_room` (warning).

**Particles are opaque palette colours** (decided by the Owner, 2026-11-12). The dust is drawn additively at alpha 0.55, so
its pixels are neither binary nor on the palette, whatever colours Kiripix gives. New particle kinds (steam, drips, splashes)
draw opaque, in the emitter's `colours`, so the list holds. Moving the dust over is the game's choice.

## (b) and (c): Loops

A **Loop** (in [the glossary](../../GLOSSARY.md), kept by the Owner, 2026-11-12): a part of a Room that plays by itself, over and over, cut to a region.
It is either a colour **cycle** or **frames**. Its frame 0 is always the room's own pixels, so a paused room, a capture at
frame 0 and the Plate test are all unchanged.

### Where it lives

A new Stage, **`loops`**, after `looks` and before `place`:
**… → palette → looks → loops → place → reach → export**. With no Loops it is `done`, like `looks`. `place` and `reach` read the
room without its Loops: a Loop never changes collision, Masks or Markers.

**Not an animated Look** (decided by the Owner, 2026-11-12). A Look is hidden and appears when the game's state says so; it replaces part of the
room. A Loop is shown at once and plays forever; its first frame is the room. Their Checks differ too (a Look must change its
region; a Loop's frame 0 must not). So they are separate Stages that share code. The edit pipeline from `looks` (resize,
register, fit, regrade, map, cut, split by Layer) moves into one module in `recipes`, and the region Decisions (`polygon`,
`brush`, `difference`) become shared too. `loops` adds `flood` (colour region within an OKLab tolerance, as on `masks`), which
picks a neon tube or a puddle's highlights in one click.

### Decisions, in target pixels, each naming its Loop

- `loop`: ID, form (`cycle` or `frames`), `layer` (`plate`, the default, or a foreground Layer's ID), an optional `light` (a
  light Marker ID for the game to flicker on the same sequence; decided by the Owner, 2026-11-12) and an optional `phase` (a start offset in ticks,
  so two clocks don't tick together).
- region: `polygon`, `brush`, `difference`, `flood`. The region is the Loop's binary alpha, not a Mask.
- `cycle` (form `cycle`): which colours cycle (clicked from the room or picked from the palette, in order), and a mode:
  - `rotate`: classic colour cycling. The k chosen colours move one place along the list each step (water, a marquee, a neon
    chase). The region's average brightness stays about the same.
  - `pulse`: each region pixel steps along its own ramp, from the palette's OKLab lightness order within its hue, by up to n
    steps and back (a screen's glow, a tube's flicker). This one changes brightness (see "Option A", below).
- `frames` (form `frames`): where the frames come from, see "Making frames".
- `timing`: ticks per frame (whole 60 Hz physics ticks, never seconds), or a list per frame; `pingpong` (0 1 2 1, which hides a
  seam and halves the frames to make); or `flicker` (a seed, a mean and a spread), which Kiripix expands at build time into a
  fixed sequence of (frame, ticks) pairs. The game never rolls dice for a Loop: it plays the list, so replays are exact.

### Making frames for $0 (route c)

In the order of the Owner's time:
1. **From an Op** (about 1 to 3 minutes: choose a Layer or region, an Op, an amplitude, a frame count; preview). Pure Ops in
   `ops`, golden-tested, whose output pixels are copies of input pixels, so frames are on the palette by construction:
   - `sway(layer, anchor_row, amplitude, frames)`: each row shifts by whole pixels, more the further it is from the anchor
     (a plant from its pot, a curtain from its rod). It needs the object as a foreground Layer, because the pixels it uncovers
     must come from the Plate's fill. On a Plate region nothing lies behind the object, so the Stage refuses (`loop.no_fill`)
     and the finding names the `layers` Decision that lifts it out.
   - `shimmer(image, region, amplitude, wavelength, frames)`: rows inside the region shift by up to a pixel in a travelling
     wave (water, heat).
   - `scroll(image, region, dx, dy, frames)`: the region's pixels move and wrap within it (rain on glass, a conveyor, a
     marquee of text).
2. **A hand-painted kit** (5 to 20 minutes for a small object). `kiripix loop kit <id> <loop> <folder>` writes the region's box
   at target size (frame 0, mapped), N−1 copies to paint on, and the palette as `.gpl` and a swatch PNG, for any pixel editor
   (Aseprite, or the free LibreSprite and Pixelorama). `kiripix import <id> <png…> --loop <loop>` reads them back. There is no
   registration, because the frames are painted on the target grid. This suits a fan, a clock, a board's flaps: small things
   with a few frames.
3. **Image-model edits of the Source** (3 to 5 minutes a frame, plus the model's wait). One edit per frame, "Edit this image.
   Keep everything exactly the same except: …", imported with `import <id> <png> --loop <loop> --frame <n>` and picked as a
   Variant, then built through the Looks pipeline. Each edit drifts on its own, so smooth motion will flicker; expect it to work
   only for 2- or 3-frame changes (a curtain in or out, a TV picture, a board's flaps). The trial measures this.

### Loops and foreground Layers

- **`layer = plate`:** the frames are opaque within the region and draw with the Plate, under every actor. Pixels inside a
  foreground Layer's alpha become a piece for that Layer, cut by the Layer's own (still) alpha, as for a Look.
- **`layer = <id>`:** the Layer itself animates. Its frames carry their own alpha: where the swaying plant moves away, the Plate's
  fill shows through. They draw at the Layer's depth and sort by its y-sort line. Edit-made frames have no alpha of their own, so
  on a Layer they are cut by the Layer's still alpha, and motion past its silhouette needs an Op or a kit (`loop.past_layer`,
  a warning, counts the pixels lost).

### Option A: does a brightness cycle re-light the painting? (decided by the Owner, 2026-11-12: the proposal below holds)

The rule exists for two reasons: light computed onto a baked painting looks wrong, and the Plate must stay pixel-identical. A
Loop keeps the second, because the Plate node is untouched and frame 0 is the Plate. The first depends on where the change is:
- **On the light source's own pixels** (the tube, the sign's letters, the screen's face), a `pulse` is that object's painted
  appearance changing, as a Look's unlit lamp does. **Allowed.** The game's FX layer already draws additive glows and
  emissive accents over the painting, which is a bigger change than a palette step.
- **On the surfaces around it** (the wall a neon sign would wash, the floor under a TV), a `pulse` is re-lighting the painting
  by another means. **Not allowed.** That light reaches actors only, through the light Marker's
  `PointLight2D`, which the game flickers on the Loop's sequence (`light`).

Kiripix can't tell a light source from a wall, so it records the Owner's intent: a `pulse` Loop has an `emissive` flag
(`true` by default) and `loop.pulse_spills` (info) flags a pulse region more than a few pixels wider than the colours it picked.
A `rotate` cycle keeps the region's average brightness, so it is animation, not light. **The game's side:** DEC-018 and
`TECHNICAL.md` §3 get this line (a game ticket) before the first `pulse` ships.

### Checks

- `loop.off_palette` (error): a frame pixel off the palette.
- `loop.frame0` (error): frame 0 differs from the room inside the region. By construction for cycles and Ops; for kit and edit
  frames, Kiripix takes frame 0 from the room and never imports it, so this guards a bug.
- `loop.misaligned` (error), `loop.drift` (warning): as `look.misaligned` and `look.drift`, for edit frames, per frame.
- `loop.outside_region` (warning): a kit frame changed pixels outside the region; they are cut away, and the finding says where.
- `loop.seam` (warning): the change from the last frame to frame 0 is much larger than the median change between frames, so the
  loop pops. Its `fix` is `pingpong`. For a cycle, the largest OKLab step in the colour list is at the wrap.
- `loop.still` (warning): a frame equals the one before it (the timing should hold it instead), or no frame differs from frame 0.
- `loop.flash` (error, for now; decided by the Owner, 2026-11-12): more than three large brightness changes a second over a
  large share of the screen, the WCAG 2.3.1 general flash threshold, scaled to 640×360. A fast flicker on a big sign trips it.
  Its `fix` is a slower `timing`.
- `loop.overlaps_look` (warning): a Loop's region meets a Look's region. When that Look shows, the game hides the Loop by its ID,
  from its own room data (decided by the Owner, 2026-11-12); Kiripix only warns.
- `loop.no_fill` (error), `loop.past_layer` (warning), `loop.pulse_spills` (info): above.
- `loop.texture` (info): the room's Loop textures in bytes and frames, for the game's per-room effects budget.

**Staleness**, as for Looks: a new Source puts edit frames in `needs-input`; a refit puts kit frames in `needs-input` (painted
on another grid) and edit frames and `difference` regions in `needs-review`; a palette change remaps kit and edit frames
(`needs-review`) and rebuilds cycles and Op frames (`done`). Loop IDs freeze on export, like Look IDs.

### Export

**Cycles are baked into frames** (decided by the Owner, 2026-11-12): Kiripix writes every distinct frame of a cycle, so the game has one player for
(b) and (c), no shader, and nothing to get wrong in GLSL on the Compatibility renderer. A cycle has k frames (`rotate`) or a few
distinct ones (a flicker of on, dim and off with a long sequence), which costs a few KB. A runtime index-and-palette shader
stays possible from `room.json`'s data if a Loop is ever too large to bake.

- **Files:** `loops/<loop>.png`, the frames side by side (wrapping into rows past 4096 px); a piece per foreground Layer as
  `loops/<loop>.<layer>.png`; for a cycle, also `loops/<loop>.index.png` (8-bit: 0 outside the cycle, i + 1 for the cycle's
  i-th colour).
- **Scene:** a `Loops` node drawn with the Plate (the game's wrapper moves it onto the background layer with the Plate, so no
  light reaches it), with a `Sprite2D` per Loop at its region's box: `hframes` (and `vframes`), `frame = 0`, visible, unshaded,
  and metadata `kiripix_id`, `kiripix_type = "loop"`, `sequence` (`PackedInt32Array` of frame, ticks pairs), `phase` and, when
  set, `light`. A piece is a `Sprite2D` child of its Layer's node with the same metadata. A Loop with `layer = <id>` replaces that
  Layer's texture with its strip and gives the Layer's node the metadata, so the Layer and its motion are one node.
  **Not `AnimatedSprite2D`:** it advances on its own clock, and the game must advance frames from its frame counter.
- **`room.json`** (next `schema_version`): `loops`: ID, form, layer, box, file, frames, `sequence`, phase, light or `null`,
  pieces (layer, file, box), and for a cycle the index file, colours and mode.
- **The game's side** (to raise in its backlog, not Kiripix work): its room wrapper sets each Loop node's `frame` from
  `(frame_counter + phase)` through the sequence in `_physics_process`; a dev hook holds every Loop at frame 0 for the Plate
  test and captures; particle kinds for steam, drips and splashes; light flicker from a Loop's `sequence`.

## (d) Animated actors

No Kiripix work. A separable object with its own frames is a `sprite` Asset (0174, in M4), exported as a character; the room
gives it a Spawn or an interactable Marker; the game places it, lights it as an actor and y-sorts it by its feet. It must not
also be painted into the room, so the room is painted (or lifted with `layers` and inpainted) without it. "A Prop with frames"
would duplicate the `sprite` Kind and isn't proposed.

## (e) Why not a shader on the Plate

- A shader on the Plate node changes the node that must be pixel-identical to the export, and the game's test fails whenever
  it runs.
- Godot's `TIME` is wall-clock, so a shader that uses it is not deterministic. A uniform set from the frame counter fixes that.
- A UV-distortion shader samples between texels, so even with nearest filtering it duplicates and drops pixels unevenly.
  Integer offsets via `texelFetch` avoid that.

**A pixel-safe form does exist:** a separate sprite over the region (a copy of the Plate's pixels), with a shader that moves
texels by whole pixels and takes its phase from a uniform the game sets from the frame counter. That is exactly what
`sway`, `shimmer` and `scroll` bake at build time. Baking is better here: the Ops are golden-tested, the Kiripix UI can preview
them, and the game needs one player, not a shader per effect. A runtime shader is worth it only for a large region where baked
frames get heavy (a full-screen rain sheet); file it then.

## Estimates

Calibrated on the M4 Looks tickets (0130: 200–300k tokens, plus 100–150k for its UI) and the join tickets (250–400k).

| Route | Tickets | Tokens | Notes |
|---|---|---|---|
| (a) Emitter shape, direction, colours | 3: `place` fields and Checks (core); export (export); the UI to draw them | 280–500k | Game work per particle kind is separate. The coffee needs no Kiripix work at all if the game types its own polygon and colour. |
| (b) Cycles, built first | 4: the `loops` Stage with shared region Decisions and the edit module moved out of `looks` (core); cycle Ops and the flicker sequence (imaging, goldens); export and `room.json` (export); the loops screen with a live preview at 60 Hz ticks (UI) | 650k–1.0M | Carries the Stage skeleton, export and Checks that (c) reuses. |
| (c) Frames, on top of (b) | 5: frame Ops `sway`, `shimmer`, `scroll` (imaging); the kit, `import --loop` and the frame Checks (core); edit frames through the Looks pipeline (core); animated Layer export (export); the frame strip in the UI (UI) | 750k–1.2M | Built alone, without (b), add about 200k for the skeleton. Edit frames are the last and most cuttable ticket. |
| (d) Animated actors | 0 | 0 | The `sprite` Kind (0174). |
| (e) Shader on the Plate | 0 | 0 | Not recommended. |
| ADR draft for the `loops` Stage | 0 (with 0189) | 30–60k | The split itself is done; the tickets follow. |
| Trial ([0184](0184-m4-ambient-animation-trial.md)) | 1 | 80–150k | Main session, no new code. |

Whole: about 1.8–2.9M tokens for (a), (b) and (c), close to M2's props.

## Recommendation

1. **Now, with no Kiripix work: the coffee.** The kitchen's steam is a game ticket (a `steam` particle kind at an emitter
   Marker, its polygon and colour in the game's room data, as the dust is). That's the Owner's headline example, live before any
   of this is built.
2. **The trial (0184).** It measures the Owner's time and verdict on one (b) and one (c) in a real room.
3. **First Kiripix build: (b) cycles,** unless the trial says otherwise. It costs the Owner a few minutes and no images per
   Loop, it is pixel-exact by construction, it covers the most examples (tubes, signs, screens, water, boards), and it builds the
   Stage, export, Checks and game player that (c) reuses.
4. **Then (c),** frame sources in the order Op, kit, edits. Op frames need no images at all; edits are the most expensive and the
   least likely to loop cleanly, so they come last and may be cut.
5. **(a)'s two tickets,** independent of the rest, before the game writes its second particle kind (drips or rain), so shapes
   stop being typed into the game's data.

All of it is in M4 (the Owner, 2026-11-12).

## User Stories

1. As the Owner, I want to make a neon sign flicker by clicking its tube and picking a timing, so that a room feels alive
   without my making any image.
2. As the Owner, I want a plant to sway from a Layer and a slider, so that motion costs me a minute, not a drawing.
3. As the Owner, I want a kit of the region at target size and the palette for my pixel editor, so that I can paint a fan's 3
   frames myself and have them checked.
4. As the Owner, I want to be told when a loop pops at its seam, drifts outside its region or flashes too fast, so that I don't
   find it in the game.
5. As the Owner, I want a Loop on a foreground Layer to sort with that Layer, so that the player still walks behind the plant.
6. As the game, I want every Loop's frame 0 to be the room and its timing in whole ticks, so that the Plate test and replays stay
   exact.
7. As the game, I want an emitter's shape, direction and colours drawn on the room, so that a moved tap moves its drip.
8. As an agent, I want the Loops in `room.json`, so that another Exporter can play them without parsing a Godot scene.

## Decisions (the Owner, 2026-11-12)

1. **Milestone:** M4, every route: (a), (b), (c) and the trial.
2. **Option A:** a `pulse` may change the brightness of a light source's own pixels (tube, sign, screen); the surfaces around it
   never change, and light reaches actors only. The game's DEC-018 and `TECHNICAL.md` §3 get the line (a game ticket).
3. **Particles on the palette:** new particle kinds draw opaque, in the emitter's palette `colours`.
4. **The word:** "Loop" stays. A character clip's `loop` is a lower-case flag on another Kind's Decision, while a Loop is a
   room's, with its own Stage, Decision and `--loop` flag on `import`, so a CLI agent meets them in different places. The
   glossary entry says which is which, and `describe` for the `loops` Stage names the clip flag as something else.
5. **Separate Stage:** `loops` beside `looks`, sharing the edit module and the region Decisions.
6. **Baked cycles:** Kiripix bakes a cycle's frames, and the game has one player. `room.json` keeps the index image and colours.
7. **Flashes:** `loop.flash` is an error for now.
8. **Loops and Looks:** the game hides a Loop by its ID when a Look over it shows, from its own room data; Kiripix warns about
   the overlap. A Loop that belongs to a Look waits for a room that needs it.
9. **Light sync:** a Loop may name a light Marker (`light`), and the game flickers that `PointLight2D` on the Loop's `sequence`.

## Out of scope

Loops that change collision, Masks or Markers; Loops that stack with Looks; a runtime shader route; sound (the game's
`ambience`); generating frames with a Provider (M6); "a Prop with frames".
