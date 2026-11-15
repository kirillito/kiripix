---
status: done
milestone: M4
agent: character-pipeline
type: trial
parent: ../m5/0152-m5-character-layers.md
---

# M4: trial: base Models built by Claude in Blender

Spec §6.3 (model) and §16 (open decision 4, image-to-3D). Asked for at the M3 gate ([0117](../m3/0117-m3-gate.md)),
2026-11-11.

## Background

mc02 was built by a scripted Blender session: Claude, headless, reshaping a Quaternius base and modelling the clothes.
At the gate the Owner found Fable 5.2 "much better than expected" at this, better than Opus, and wants to make it part of
making a character, at least for one with many animations. Of the 120 minutes the Owner spent on mc02, most went into getting
and choosing a Model and the Mixamo round trip, not into Kiripix.

The game's customisable MC needs two bodies, one per gender ([0152](../m5/0152-m5-character-layers.md)), with hair styles and
outfits as layers over them. So the base Models should be bodies in underwear only, with anime-style eyes large enough to
survive 52 px (Sea of Stars, Chrono Trigger), and nothing a layer will cover.

## What to do

1. With Fable, build a **male and a female base Model** in headless Blender: underwear only, large eyes, a material per part
   (skin, eyes, hair, underwear), so M4's ramps per part ([0147](0147-m4-character-palette-ramps.md)) and M5's layers
   work. Keep each session's script with the Model, so it can be run again or revised.
2. Take each through Mixamo's auto-rig and Kiripix to export with mc02's clips, and look at it in Godot beside mc02.
3. Check what the layers trial ([0153](../m5/0153-m5-character-layer-trial.md)) needs from a base, such as clean shoulders and
   hairline for hair and outfits to sit on, and whether one session can also build a hair style or an outfit as its own
   mesh on the same skeleton.

## What to record, in this ticket

- Time per base Model: prompting, the sessions, review, Mixamo, Kiripix. Tokens if the session reports them.
- What went wrong and how often (a broken rig, wrong proportions, eyes that vanish: [0159](0159-m4-part-vanishes-check.md)).
- Where the scripts and Models live, and whether Kiripix should keep the script as a source file of the Model.
- The Owner's choice: this as the way to make bodies, and whether Kiripix needs anything for it (a ticket for each).

## Acceptance criteria

- [x] Two base Models, rigged and rendered, their paths listed here, with the numbers above.
- [x] The Owner's choice recorded.

## Generator trial, 2026-11-14 (session log; resume from here)

The trial grown into a generator: a parameter file → headless Blender → a rigged GLB with one material per part → a Kiripix
character with mc03's clips. Asked for by the Owner; timeboxed to one session. Everything is in the art repo
(`urban-mystery-club-art/chargen/`, read its `README.md` first); nothing in Kiripix's code changed. Paths below are in the
art repo.

### State after steps 1 to 3 (bases, parts, parameter format): done

- **Bases:** `chargen/bases/adult_male.fbx` and `adult_female.fbx` are mc03's two underwear bodies on their Mixamo rigs
  (copies of `[assets]/mc03/mc03_<body>_sprite_rigged.fbx`), with the scripts that built them in `chargen/bases/src/`.
  `chargen/npcs/base_male.toml` and `base_female.toml` build them unchanged.
- **Shape:** `build` (-1 thin to 1 heavy), `age` (0 to 1 elderly) and `height`, plus 24 low-level values, in
  `shape_values()` of `chargen/generate.py`. The shape is a pose of the base's Mixamo skeleton (bone scales, and rotations
  for posture), applied to the mesh and then made the rest pose (`apply_shape()`). **No new Mixamo trip:** bone names
  and hierarchy are unchanged, so mc03's clip sources apply by name, and a posture baked into the rest pose stays in every
  clip (a clip's rotations are relative to rest). One shape is not a bone scale: the belly (the waist's front moved
  forward). No shape keys were needed.
- **Parts** (`chargen/library.toml`): hair `short` (the base's own), `buzzed`, `parted`, `long`, `buns`, and `beard` (kit,
  CC0); tops `tee`, `sweater`, `jacket` (open, shows `under`), `coat` (long, with a skirt), `parka`; bottoms `trousers`,
  `shorts`, `skirt`; shoes `sneakers`, `boots`; hats `beanie`, `cap`, `flat_cap`, `brim_hat`. Clothes are the body's own
  faces, painted and pushed out, so their weights are the body's; hair and hats follow the head; skirts are tubes weighted
  to the hips and thighs.
- **Materials are slots** (`skin`, `hair`, `eyes`, `top`, `under`, `bottom`, `shoes`, `sole`, `hat`), not garments, so
  `parts` is the same list of names on every character.
- **Parameter file:** TOML, `chargen/npcs/<name>.toml` (base, `[shape]`, `[parts]`, `[colours]`); format in the README.
- **Measured:** `generate.py` builds a character in 1.1 to 2.7 s; the first working build of two characters came 20 minutes
  into the session.
- **A rigged GLB is accepted as the Model with no `--role rigged` file:** `rig` validates the Model's own armature and
  `clips copy` brings mc03's clips. Checked on `character.npc_elder_coat`: model to export in 92 s.

Open problems after step 3:
- Kit hair on the female base sat 3 cm too low (bald crown); `generate.py` now stretches a hairstyle's box until the
  scalp's is inside it. A few scalp faces still show through `long` and `buns` in Blender; not seen at 52 px.
- A brim wider than about 5 cm hides the eyes at the 30° look-down, and `finish`'s stamped eyes are then painted on the
  hat. `brim_hat` is kept narrow; see the proposals below.

### State after steps 4 and 5 (six NPCs through Kiripix, the contact sheet): done

- **Six NPCs,** each `chargen/npcs/<name>.toml` → `assets/character/npc_<name>/`, built to the `export` Stage with
  `palette` `parts` set (nothing exported into the game): `elder_coat` (elderly man, long coat, flat cap; 48 px),
  `heavy_woman` (build 0.9, sweater, skirt, buns; 50 px), `thin_teen` (build -0.8, bigger head, narrow shoulders, T-shirt and
  shorts; 48 px), `big_man` (build 1.0, parka, beanie, beard; 56 px), `elder_woman` (age 0.9, long coat, white bob; 47 px),
  `tall_woman` (build -0.5, long hair, open jacket over a T-shirt; 55 px).
- **The contact sheet:** `chargen/sheets/cast.png`: the six beside `mc03_male_clothes01`, `mc03_female_clothes01` and
  `sanjay`; idle and two walk frames in `s` and `sw`, at 3x and 1x, from each character's exported `color.png`.
  `chargen/contact_sheet.py` rebuilds it.
- **Range,** from a Blender preview with walk, idle and attack poses (`chargen/sheets/range_preview.png`, files in
  `chargen/npcs/range/`): thin holds to -1.3; elderly to 1.4; heavy holds to about 1.1 (at 1.4 the walk's arm swing passes
  through the belly in profile, although `arms_out` holds the arms away in idle); longer legs and a smaller head hold. A
  child's proportions (head 1.28, legs 0.72) play the clips without breaking but read as a short adult with a big head: a
  child needs its own base body and, to look like a child, its own clips. No child base was built.
- **Kiripix findings on the six:** only warnings: `clips.root_motion` (the base's walk, as on mc03), and
  `sheet.part_vanishes` in `attack` for hair under a hat and for the `under` shirt seen from the side. No
  `palette.ramp_shared`.

### Numbers

| | Session | Blender and Kiripix | Owner |
|---|---|---|---|
| A new NPC, bases and parts existing | writing one parameter file (a minute or two each; the six were written in one go, not timed apart) | build 1.1 to 2.7 s; preview about 4 s; Kiripix model to export 75 to 98 s (3 clips, 8 directions) | none, apart from looking |
| This trial, from nothing to the first sheet of six | about 35 to 40 minutes (to 01:51), then about 10 minutes of fixes | about 14 minutes of Kiripix in all (10 runs) | none |
| mc03, two bodies ([assets]/mc03, by file times) | 17:26 to 20:19 on 2026-11-12, 13 preview rounds | Kiripix runs of 60 to 130 s | the Mixamo trip: 27 minutes between `model` and `rig` in mc03_male's history |
| mc03 clothes01, both bodies | one round; under 20 minutes by file times | 2 runs of about 60 s | none (rerig.py) |
| Sanjay ([assets]/party_sanjay) | 7 rounds; r1 at 00:19, rigged at 00:41 (start not recorded) | one run of 86 s | none (rerig.py) |
| A PixelLab character | no time is recorded in either repo, so there is nothing to compare with | | |

### What went wrong, and how often

- Kit hair too low on the female base (1 of 2 bases), fixed in `generate.py`; scalp showing through a parting (2 of 6),
  fixed by drawing the scalp in under kit hair.
- A wide brim, then a cap over a beard, hid the face (1 of 6, twice): the stamped eyes were painted on the hat.
- A pale shirt read as bare skin in an open jacket (1 of 6): a colour choice, not a bug.
- Not checked: the NPCs in Godot; the `attack` clip's frames in Kiripix (only in the Blender preview); a ramp swap in the
  game; directions other than `s` and `sw` in Kiripix's frames.

### Proposals for Kiripix (no Kiripix code was changed)

- [0165](0165-m4-characters-share-a-base.md): notes from this trial are added there (a generated Model changes the rest
  proportions on purpose; a rigged Model needs no rigged file; height from the Model).
- [0224](0224-m4-a-model-built-from-a-parameter-file.md): a Model built from a parameter file by a script, as a
  rebuildable source.
- [0225](0225-m4-stamped-eyes-on-a-covered-face.md): `finish` stamps eyes on a hat that covers them.
- [0226](0226-m4-cast-sheet-probe.md): a cast sheet of several characters, as a Probe.

### The Owner's choice on the generator (2026-11-14)

The generator goes on: "I like generated characters in test results as a first step". Kiripix builds
[0165](0165-m4-characters-share-a-base.md) (a base) and then [0224](0224-m4-a-model-built-from-a-parameter-file.md)
(a Model from a parameter file); the design is [ADR 0012](../../docs/adr/0012-a-character-can-be-made-from-a-base.md).
Both were built on 2026-11-14. What is left is in the art repo: the bases and the NPCs' `base`, and `generate.py`'s
arguments (each ticket's "For the art repo").

### What's next (for the session that picks this up)

1. The Owner judges `chargen/sheets/cast.png` and records the choice here.
2. If it goes on: clip variants first (they are what makes the cast look alike), then parts, then a child base. The plan
   is in the session's final report and in the tickets above.
