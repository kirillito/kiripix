# A room's Loops are a Stage beside its Looks

A painted room reaches the game as one still picture, and the Owner wants parts of it to move: a flickering tube, a TV's
glow, a swaying plant, a clock (ticket 0183). We call such a part a Loop (glossary): a part of a Room that plays by
itself, over and over, cut to a region, either a colour cycle or frames. Its frame 0 is the room's own pixels, so a paused
room, a capture and the game's Plate test are unchanged. We considered four places for it:

1. **A Look that animates, in `looks`.** It would reuse the edit pipeline and the region Decisions. But a Look is hidden
   until the game's state shows it, and it replaces part of the room. A Loop shows at once and plays forever, and its first
   frame is the room. Their Checks contradict each other: a Look must change its region (`look.unchanged`), while a Loop's
   frame 0 must not (`loop.frame0`). And most Loops need no edit at all (colour cycles, Op frames, hand-painted kits),
   while `looks` waits in `needs-input` for a picked edit.
2. **A child Asset per Loop.** This was rejected for the reasons ADR 0009 gives for Looks. It would repeat `fit` and
   `palette`, read another Asset's Grid transform, palette and Layers, and need inputs that cross Assets.
3. **A shader on the Plate, in the game.** It changes the node the game tests as pixel-identical to the export. Godot's
   `TIME` is wall-clock, and a UV shader drops and doubles pixels. A pixel-safe shader would move whole texels by a phase
   the game sets from its frame counter, and that is what baking does at build time, with golden tests.
4. **A `loops` Stage of its own after `looks`**, sharing the region Decisions and the edit pipeline with it through one
   module, `recipes/regions.py`.

We chose 4 (the Owner, 2026-11-12; 0183, Decision 5): room: brief → source → fit → layers → masks → palette → looks →
**loops** → place → reach → export.

A `loop` Decision declares a Loop: its ID, `form` (`cycle` or `frames`), `layer` (the Plate or a foreground Layer, whose
alpha cuts it), an optional `light` and a `phase` in ticks. Its region is `polygon`, `brush`, `flood` or `difference`, the
code `looks` uses. A colour cycle steps chosen palette colours through a list (`rotate`) or lifts each pixel along its own
ramp and back (`pulse`). A frame Loop's frames come from an Op on the room's own pixels (`sway`, `shimmer`, `scroll`) or
from a kit painted at target size. `timing` is in whole ticks, never seconds: `ticks`, `pingpong`, or a seeded `flicker`
that Kiripix expands at build time. Each Loop gets a fixed `sequence` of (frame, ticks), and the game never rolls dice.

## Consequences

- **The Stage's inputs.** `loops` reads `layers`, `palette`, `source`, `fit`, `masks` and `looks`, plus the `palette` and
  `project.resolution` settings. It calls no Runner, so ADR 0004 holds: a palette change rebuilds cycles and Op frames
  (`done`). Kit frames are remapped to the new palette, and the Stage goes to `needs-review` until `accept` re-records the
  kit. A `flood` is measured on `fit.png`, before the palette, so a palette change doesn't move a region. A refit or a
  Layer change replays it into `needs-review`. A refit holds a kit painted on the old fit.
- **`place` and `reach` don't read `loops`.** A Loop never changes collision, Masks or Markers. A room with no Loops has
  a `loops` Stage that is `done` at once. Adding the Stage made `export` stale for every room, which was a deterministic
  rebuild.
- **A Loop's `light` is a plain light Marker ID** (Decision 9). The game flickers that `PointLight2D` on the Loop's
  `sequence`. Light Markers are placed in `place`, which runs after `loops`, so `loop.light_unknown` can't be a Check of
  `loops`. It is an `export` Check, and `export` reads `loops` upstream.
- **Frame 0 is always the room.** The game has one player. It sets each Loop sprite's `frame` from its frame counter plus
  `phase`, through `sequence`. With `timing.rest`, frame 0 is a rest frame that `sequence` never plays (a screen that is
  off in the room doesn't go dark on every loop). It is still frame 0 of every strip, and the scene still sets
  `frame = 0`, so the Plate test is unchanged. `loop.seam`, `loop.still` and `loop.flash` measure the played sequence.
  Since ticket 0403, a frame Loop on the Plate stores frame 0 as clear pixels: its strips keep only what differs from frame
  0 (in every piece, a Layer it crosses too), and the room under the sprite is frame 0. An unshaded sprite then never
  covers a lit Plate with the room's unlit pixels (trial 0402: a dull box under a light). A Loop on a Layer keeps whole
  frames, because its frame 0 is the region its Layer's remainder clears (below), so moved-away pixels show the Plate's
  fill. The checks still read whole frames.
- **Cycles are baked into frames** (Decision 6). Kiripix writes every distinct frame, so cycles and frames share one
  player and no shader. `room.json` keeps a cycle's index image, colours and mode, so a runtime palette shader stays
  possible if a Loop is ever too large to bake.
- **A `pulse` lifts by OKLab lightness** (`lift`, default 0.15), not by places along a ramp. The same `lift` then gives
  the same peak on a sparse and a dense palette. A `cycle` Decision that still gives `depth` holds its Loop, and the
  finding gives the converted `lift` (depth x 0.075). Option A stands (Decision 2): a pulse may change a light source's
  own pixels, never the surfaces around it, and `loop.pulse_spills` points at a region wider than its colours.
- **The latest Decision replaces the whole one before it.** This holds for `loop`, `cycle` and `timing` (and for
  `frames`, and a Loop's `kit`), as it does for a `marker` Decision. A changed field must be decided again with every
  other field.
- **A Loop that can't be built holds only itself.** Each reason (no cycle, no frames, a kit painted on another fit, a
  `layer` the room lacks, an ID a Look has, a timing of the wrong length, a `depth`) is one function in the Stage's list
  of held reasons. A held Loop is listed in `loops.json` with its region and reason, and reported as `loop.held` (error).
  The other Loops build. Only a Decision naming a Loop nobody declared holds the whole Stage. `export` refuses the room
  while a Loop is held (`export.loop_held`), because a Loop the game has must never vanish without notice.
- **Looks and Loops share one ID set.** The `loops` Stage enforces it: a Loop with a Look's ID is held. `decide` refuses
  a `rename` onto a taken ID (`loop.id_taken`), and `export` can't run past a held Loop. `looks` sits upstream and can't
  see the Loops, so a Look that takes a Loop's ID is caught on the Loop's side. The Manifest freezes `ids.looks` and
  `ids.loops` each on its own and doesn't enforce the set. A Stage can't read the game's Manifest. So when the clashing
  Loop was already exported, an adviser that `export` registers with core (`register_adviser`) rewrites the finding's
  advice to the only way out, which is renaming the Look. An adviser changes advice only, never a code, and adds or
  drops no finding.
- **`remove` and `rename` are Decisions of `loops`.** A pure function, given to core as the Stage's `decisions_view`,
  replays them. The build, the held reasons, the ID set and the freeze therefore all see the IDs after replay. The input
  hash and `show` still read the journal as recorded. A renamed kit keeps its frames under the folder of its first ID
  (`was`). Removing or renaming an exported Loop is refused before it is recorded (`export.id_frozen`). Loop IDs freeze
  on export, like Look and Layer IDs (ADR 0003).
- **Loops and foreground Layers.** On the Plate, a Loop's pixels inside a foreground Layer's alpha become a piece for
  that Layer, as for a Look. On a Layer, the Loop is cut by the Layer's alpha, and `sway` needs a Layer (`loop.no_fill`
  on the Plate). In the scene, a Layer's own `Sprite2D` shows a Loop's strip (`moves_layer`) only when the Loop is a frame
  Loop that covers every opaque pixel of the Layer and is the only frame Loop with a piece on that Layer. In every other
  case the Layer's `Sprite2D` shows a remainder (the Layer with each frame Loop piece's frame-0 pixels cleared), and the
  strips are its children, so the Plate's fill shows where a frame moves away. Colour cycles, and a Plate Loop's pieces
  over a Layer, are child pieces as before and need no remainder. This replaces ticket 0195's "the first such Loop by ID", which left the other Loop's moved-away
  pixels showing.
- **Loop data lives in `room.json`** (schema 10), not only in the Godot scene, so a second Exporter reads the same thing.
  Loops share the room's journal and lock, as Looks do.
- **When a Look over a Loop shows**, the game hides the Loop by its ID, from its own room data (Decision 8). Kiripix only
  warns (`loop.overlaps_look`).
- **Edit frames** (Loop frames made as edits of the Source, picked per frame; tickets 0219 and 0220) go through the edit
  pipeline a Look's edit does (`fitted_edit_file`, with the `looks` Stage's own parameters): resize, register, fit, regrade,
  map the whole edit once, cut to the region. An edit has no alpha of its own, so on a Layer the frame is cut by the Layer's
  alpha. A `hold` Decision keeps a part of the region still: in frames 1 on, it takes the pixels of the frame it names.
  An edit-frame Loop whose region redraws is a boiling picture (trial 0184), so `loop.flicker` measures the share of the
  region outside every `hold` that changes between consecutive edit frames.
- **Still open:** a `pulse` pixel already at its ramp's light end doesn't move, and only `loop.still` notices, when no
  pixel moves at all. `loop.flash` measures area against `project.resolution`, not against what the game's camera shows.
  A `flicker` has no seam measure.
