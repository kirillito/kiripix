---
status: done
milestone: M6
agent: imaging-engineer
type: trial
---

# M6: trial: a room's frame Loops painted by Pixelbolt

Spec §6.1 (`loops`), ADR 0011 and §14. Written by the Owner's request on 2026-11-27, after the effects trial
[0347](0347-m6-vfx-trial.md) found [Pixelbolt](https://github.com/skulitom/Pixelbolt) (MIT, Node 20+, no GPU) good at particle
and fluid motion on a fixed palette.

**Nothing from this trial goes into the Kiripix repo:** no images, sheets, scratch Projects or scripts, and no names of the
Owner's game, rooms or art. Work in the Owner's art Project (on a copy) or the session's scratchpad. This ticket's Result records
numbers, settings and findings in generic words ("a top-down room with a wall torch"); the pictures are listed by path outside
the repo for the Owner.

## The question

A frame Loop's frames come today from Ops on the room's pixels (`sway`, `shimmer`, `scroll`), a kit painted by hand at target size
(`loop kit`, then `import --loop`), or edits of the Source. Hand-painted kits cost the Owner's time and the Ops can't make fire,
smoke or falling water. Can Pixelbolt paint a kit: frames at the region's size, on the Project palette, that loop without a jump
and sit in a painted room? For which kinds of motion, and how many recipe edits does each take?

## What to do

1. **Five Loops** in one or two of the Owner's painted rooms, chosen with the Owner to span the need: a flame (a torch or a
   candle), smoke or steam rising, water (falling, dripping or a surface ripple), a flicker or glow (a lamp, a screen), and one
   the Owner names. Record each one's region size, frame count and timing.
2. **For each:** `kiripix loop kit` writes the kit. Pixelbolt makes the frames, always with its latest release
   (`npx -y pixelbolt@latest`, the Owner, 2026-11-27):
   - start from a shipped preset where one fits (`pixelbolt presets --find "torch"`, `"smoke"`, `"water"`), compiled at the
     region's size (`compile --preset <name> --size WxH --frames N`), or a `pixelforge-fluid` / `pixelforge-fx` source written
     by Claude;
   - the room's own pixels as the background where the motion is drawn over them (`pixelbolt import` of the kit's frame 0 to a
     recipe, then layers on top), or the motion alone on transparent pixels where the Loop's region cuts it;
   - the palette typed from the Project palette (Kiripix's `palette` and the Loop's off-palette check are the guard);
   - `pixelbolt inspect` (contact sheet, `--animation <name> --every <ms>`) to look at it, and its `tile` view where a Loop
     wraps or scrolls.
   Then `import --loop` the frames, with `timing` `ticks` from Pixelbolt's frame durations, and `run`.
3. **Check with Kiripix:** the Loop's checks (off-palette share, alpha 0 or 255, strokes outside the region, the wrap has no jump,
   the flash rate, frame 0 is the room inside the region), and the Loop in the walk test and in Godot over the room, lit and
   unlit.
4. **Compare** each with the route the Owner would otherwise take (a hand kit, an Op, or an edit Loop), on the Owner's view of
   the GIFs: kept or not, and Pixelbolt's recipe edits per Loop. No timing of the Owner's work against an older milestone.
5. **What Kiripix would need,** if Pixelbolt wins for some kinds: whether importing a Pixelbolt render into a Loop directly (its
   atlas's frames and durations, as [0401](0401-m6-import-a-pixelbolt-atlas.md) does for a `sprite`) is worth a ticket, and
   whether frame 0 must be the room exactly (a fluid drawn over the room changes frame 0) or a Loop should allow a first frame
   that isn't the room.

## What to record, in this ticket

- A table: Loop kind (generic), region size, frames, preset or source used, recipe edits, the Kiripix findings, kept or not.
- Pixelbolt's version, and the commands that made each kit (generic paths).
- The verdict per kind of motion, and the follow-up tickets proposed (not filed; the Owner decides).

## Acceptance criteria

- [x] The five Loops tried, the table filled, the Owner's verdict per kind recorded.
- [x] Nothing from the trial is in the Kiripix repo (`git status` shows only this ticket changed for 0402; the other entries are
      the Owner's edits and 0401).
- [x] Proposed follow-ups listed with `agent:` and `depends_on`.

## Result (run 2026-11-27 by the imaging agent; the Owner's verdict recorded the same day)

Everything was done on a copy of a Project in the session scratchpad (`0402/`), with Kiripix exported from commit `af1dc32`
(`git archive`, because the working tree's `import` failed at import time while 0401 was being written; see finding 8).
Nothing is in the Kiripix repo but this ticket. The Owner was not there to choose the five Loops, so I chose them from one painted
room (a top-down living room and kitchen) to span the list; **the Owner should confirm or swap them**. The pictures are in the
session scratchpad, `0402/gifs/` (each GIF and sheet carries a caption; nearest-neighbour enlargement, x3 to x8), and
`0402/pics/` for the Godot comparison.

**Pixelbolt 0.21.0** (`npx -y pixelbolt@latest`; MIT per `npm view`; Node 24.22.1; nothing installed). The earlier trial
(0347) used 0.19.0.

### The table

Frames are Pixelbolt's; the kit has one more (frame 0 is the room, a rest frame the Loop never plays; see finding 2).
Ticks come from Pixelbolt's frame durations (`round(ms x 60 / 1000)`). Recipe edits count the rounds of editing a source after
its first render. `loop.off_palette`, `loop.partial_alpha`, `loop.outside_region`, `loop.frame0`, `loop.seam`, `loop.still` and
`loop.flash` all stayed quiet for the five Loops; the only Loop finding was `loop.texture` (info: 61 frames, 10,252 bytes of PNG).

| Loop kind | Region (px) | Frames x ticks | Preset or source | Recipe edits | Kiripix findings | Kept? (my recommendation) | Owner's verdict |
|---|---|---|---|---|---|---|---|
| flame (a gas burner on a stove) | 14x12 | 8 x 6 | own `pixelforge-fluid` source, 4 colours; the `campfire` preset tried first at 14x12 came out cut | 0 | none | **keep**: a lively low flame that sits on the burner | **no**: an open flame doesn't fit this scene |
| steam (over a kettle, against a wall) | 20x22 | 12 x 7 | own `pixelforge-fluid` source, 3 pale greys dithered by density | 3 (a thin column, then a blob that covered the box, then a vanishing wisp, then a steady plume) | none | **keep, weak**: reads as steam; a plume 3 to 5 px wide at this size | **no**: out of place, and its box shows as a differently coloured rectangle (finding 4) |
| water (a faucet drip into a sink) | 12x18 | 12 x 6 | own `pixelforge-fx` source: a falling drop and a 4-fleck splash; the fluid solver pooled water over the whole basin | 1 (rewrote it from the fluid solver to particles) | none | **keep, modest**: a 1x2 px drop and a splash of a few pixels; right in kind, tiny in size | **keep**: the only Loop kept in this room |
| flicker or glow (a TV screen) | 42x22 | 8 x 6 | own `pixelforge-wave` source, 3 blues, a rolling band | 2, plus one schema slip (a threshold below 0.000001) | none | **no**: a toothed band scrolls over a dark screen; a pattern, not a glow | **no**: the TV stays switched off |
| sun-lit dust (motes over a floor patch, partly over a foreground Layer) | 50x52 (a polygon) | 16 x 9 | own `pixelforge-fx` source, 6 small emitters, 2 colours | 2 (the first made a vertical line of motes; the next was too still) | none; the strip also cut a piece for the foreground Layer it crosses, as designed | **maybe**: 1 px motes that appear and vanish rather than drift; subtle | **no** |

### Commands (generic paths; `<trial>` is the scratch folder)

```
# the Loops: loop + polygon Decisions in one file, then each kit (N+1 frames: the room, then Pixelbolt's N)
kiripix decide <room> loops --file <trial>/decl.json
kiripix loop kit <room> <loop> <trial>/kits/<loop> --frames <N+1> --force

# Pixelbolt: a source at the region's size, colours typed from the Project palette (nearest in OKLab, ties to the lowest index)
npx -y pixelbolt@latest compile <trial>/pb/src/<loop>.json --out <trial>/pb/rec/<loop>.json
npx -y pixelbolt@latest inspect <trial>/pb/rec/<loop>.json --out <trial>/pb/rec/<loop>.sheet.png     # the contact sheet
npx -y pixelbolt@latest import <trial>/kits/<loop>/frame_000.png --out <trial>/pb/rec/<room-crop>.json   # the room as a recipe
npx -y pixelbolt@latest inspect <trial>/pb/rec/<loop>.json --under <trial>/pb/rec/<room-crop>.json:idle --out <sheet>.png
npx -y pixelbolt@latest render <trial>/pb/rec/<loop>.json --out <trial>/pb/out/<loop> --gif-scale 8 --look

# into the Loop: frames 1..N, then timing in ticks with rest
kiripix import <room> <kit>/frame_001.png ... --loop <loop> --kit <kit>/kit.json
kiripix decide <room> loops --decision '{"decision":"timing","data":{"loop":"<loop>","ticks":[6,6,6,6,6,6,6,6],"rest":true}}'
kiripix run <room> ; kiripix check <room> ; kiripix export <room>      # into a scratch Godot project, never the game
```

Sources used: `pixelforge-fluid` (flame, steam), `pixelforge-fx` (drip, dust), `pixelforge-wave` (screen). `pixelbolt presets
--find "torch"` found `torch` and `wall-torch`; `"steam"` found `steam-vent`. I compiled the `campfire` preset at 14x12
(`--size 14x12 --frames 8`) and at that size it showed a corner of the logs and a lump of flame, not a flame (finding 5).

### Findings in Kiripix (each measured)

1. **A Pixelbolt render imports as it is.** Frames at the region's size with transparent pixels where nothing moves import
   directly: Kiripix lets the room show through a transparent pixel. A frame I composited over the room myself and a raw
   Pixelbolt frame built the identical strip (byte for byte). No compositing script is needed, and `pixelbolt import` of the room
   (to draw over it) is only a viewing aid (`inspect --under` showed the flame on the stove well).
2. **Frame 0 stays the room, and `rest` is the answer.** Pixelbolt's frame 0 is a motion frame, so its frame k becomes Loop frame
   k+1 and the Loop uses `timing.rest` (ticket 0222), so the quiet room never plays. Without it the paused room would be a jump
   in every cycle. A screen that is dark in the room (the TV) and a burner with no flame are natural rest frames.
3. **The guards work on Pixelbolt-shaped input.** I broke one frame on purpose: a pixel off the palette gave `loop.off_palette`
   (warning, nearest colour taken) and three pixels of alpha 102 gave `loop.partial_alpha` (error). The shipped smoke presets use
   partial-alpha colours, so they need the `dither_alpha` Op (0363) or an opaque, dithered palette as mine are. The palette is
   typed by hand from the Project palette; a 12-line script snapped my colours to the nearest one, and no pixel was off it.
4. **Whole-box strips show under a room light (the main finding).** A frame Loop's strip repaints every pixel of its box, and the
   Loop sprite is unshaded (`light_mode = 1`). Where a light Marker brightens the Plate under part of the box (a window's light over
   the steam), Godot draws a visible dull rectangle: the room's own pixels, unlit, on a lit Plate, by day and under a dark
   `CanvasModulate`. This is not Pixelbolt's doing (any kit, edit or Op Loop has it), but particle-like Loops show it most, because
   most of their box is room pixels. **Tested in the scratch Godot project:** with the pixels of frames 1 to N that equal frame 0
   made transparent (steam 4,613 of 5,280; drip 2,570 of 2,592; dust 41,528 of 41,600), the rectangle is gone in both lights and
   the glow stays bright (`0402/pics/godot_steam_box_compare.png`: whole strip against changed pixels only, day and night).
5. **A preset's `--size` cuts; it does not scale.** `compile --preset <name> --size WxH` keeps "the window holding the most of the
   drawing". For a small region write the source at the region's size (a fluid's emitter, radius and dissipation are in pixels).
6. **The fluid solver is the wrong tool for a tiny drip:** the liquid collected into a pool across the whole 12 px width. Particles
   (`fx`) did it.
7. **The wave source made a pattern, not a glow:** bands and teeth with a hard threshold; a screen's glow needs a soft ramp.
8. **The working tree at the time of the run could not run `import`:** `kiripix/commands/sources.py` raised
   `AttributeError: 'FieldInfo' object has no attribute 'AtlasRead'` when the module loaded (a field named `atlas` in `ImportData`
   shadows the `atlas` module). It is the 0401 work in progress, not a defect of 0402; commit `af1dc32` is fine. No longer
   applies: the finished 0401 loads and imports (checked 2026-11-27).
9. **Godot 4.7.2:** all five Loops play from their `sequence` in a scene I wrote (the exported `Sprite2D`'s `frame` is set from a
   tick counter), by day and under a dark `CanvasModulate`. The Loops are unshaded, so the flame, the glow and the screen stay bright
   at night, as wanted. Captures: `0402/gifs/godot_day.x2.gif` and `godot_night.x2.gif`. The walk test was not run (none of the
   Loops sits on a Mask and no Body goes through these small regions).

### The route each would otherwise take (step 4)

I did not hand-paint a kit; the Owner's view of the GIFs decides. From the Ops' definitions (spec §6.1, ADR 0011): `sway` needs a
foreground Layer, `shimmer` shifts rows sideways, `scroll` wraps pixels in the box. I tried `shimmer` on the flame's and the steam's
regions: no finding, and nothing that looks like fire or smoke (it only wobbles the burner and the wall). A colour cycle (`pulse`) is
the route for a glow.

### Verdict per kind of motion (my draft)

- **Flame: Pixelbolt wins** (0 edits; better than any Op; a hand kit would cost the Owner a painting pass).
- **Rising smoke or steam: Pixelbolt wins over the Ops, which cannot make it,** with 3 edits and a thin result at 20x22; a bigger
  region would do better.
- **Falling water or a drip: Pixelbolt works with particles**, small at this size; the fluid solver is for big regions.
- **A screen's flicker or glow: not Pixelbolt.** Use a `pulse` colour cycle or a hand-painted kit.
- **Ambient dust in light: weak.** Optional; its value is low at 1 px.

### The Owner's verdict (2026-11-27)

**For this room, keep only the dripping water.** The open flame doesn't fit the scene, the TV stays switched off, and the steam is
out of place, with its box rendered as a differently coloured rectangle (finding 4, which F1 addresses). The dust was not kept.
The other kinds aren't rejected for Pixelbolt in general: keep an eye on flame, steam and glow in other scenes; the trial shows what
Pixelbolt can do. So the per-kind verdicts above stand as findings about Pixelbolt, and the choice per room is the scene's.

### Proposed follow-ups (F1, F2 and F3 filed 2026-11-27; the rest wait)

| # | Title | agent | depends_on |
|---|---|---|---|
| F1, filed as [0403](0403-m6-loop-strips-only-changed-pixels.md) | A frame Loop's strips keep only the pixels that differ from frame 0 (frames 1 to N transparent where equal to the room), so a lit Plate shows through (finding 4); the `loops` Stage and its strips, a golden test, `room.json` unchanged. A Loop that should glow keeps its pixels because they differ. | imaging-engineer | none |
| F2, filed as [0404](0404-m6-export-loop-under-a-light.md) | Export: with a light over a Loop, check in Godot that F1 removes the box, in the room scene and in the game; a test scene. | godot-export | F1 |
| F3, filed as [0406](0406-m6-import-a-pixelbolt-atlas-into-a-loop.md) | Import a Pixelbolt atlas straight into a Loop (`import <room> <atlas.png> --loop <loop>`): its frames become Loop frames 1 to N, its durations become `ticks` (60 a second, rounded), `rest` is set, the region size is checked, the recipe is kept beside the kit in `src/`. Worth a ticket once a scene keeps more than one Pixelbolt Loop (the Owner kept only the drip here, 2026-11-27): it replaces N+1 kit frames, a tick conversion and a timing Decision that I did by script. Reuse 0401's atlas reader. | core-engineer | 0401 |
| F4 | A Pixelbolt guide for a room Loop (for Claude in the art Project, not Kiripix code): write the source at the region's size, never `--size` on a preset; opaque palette colours typed from the Project palette; liquids as `fx` particles at a small size; `rest` and N+1 frames. | imaging-engineer with the Owner | none |
| F5 | Trial: a room with a torch painted into it (frame 0 already has the flame), to see whether a Loop's first frame must be the room (below). None of the rooms I copied has one. | imaging-engineer | F3, or the Owner's pick of a room |
| F6 | `loop.flat` (info): a large region whose frames differ from frame 0 in only a few pixels, pointing at F1. Optional. | imaging-engineer | F1 |

**Step-5 questions.** (a) Importing an atlas straight into a Loop: yes, F3, small, after 0401 (it removes the tick conversion and the
N+1 shift; Kiripix already accepts transparent frames, finding 1). (b) Must frame 0 be the room exactly? I would keep the rule: it
costs nothing with `rest`, because Pixelbolt's frame 0 becomes Loop frame 1, and the Plate test, a paused room and a capture stay
unchanged. Only a torch painted into the room (F5) would argue for a first frame that isn't the room, and then the Loop would be the
painted flame's own cycle, which I did not test.

### Not done

- None of the five was a flame on a wall torch, because the rooms I copied have no torch (F5).
- Hand-kit and edit-Loop routes were not made for comparison (judged from the Ops' definitions; `shimmer` tried on two regions).
- The walk test, and a room light that flickers on the Loop's `light` (the Godot "lit" variant is a dark `CanvasModulate` over the
  room's own lights).
- No timing of the Owner's work.
