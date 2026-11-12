---
status: todo
milestone: M4
type: spec
---

# M4: a `sprite` Kind: actors from imported 2D frames

**Milestone: M4, after the palette ramps** ([0147](0147-m4-character-palette-ramps.md)), chosen by the Owner on 2026-11-12
(see "Where it goes", below). Child tickets: [0175](0175-m4-sprite-pixellab-export-trial.md) to
[0181](0181-m4-ui-sprite-screens.md).

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6.2 (prop: `fit`, `finish`), §6.3 (character), §7 (Ops), §9 (character
export), §11 (the frame strip); [the M3 character spec](../m3/0097-m3-characters.md) (names, Q5; none mirrored, Q6; the pivot,
Q10; one atlas, Q12); ADR 0003 (frozen IDs) and 0004 (Runners before the palette, outlines after it). The game's side:
`../urban-mystery-club/docs/TECHNICAL.md` §3 (lighting, normals) and §4.7, `docs/DECISION_LOG.md` DEC-004 ($0 budget),
DEC-012 (the mixed route), DEC-043 (52 px adults, body types 46–58), DEC-044 (PixelLab: a 56×56 PixFlux canvas gives ~52 px,
clean 1:1 pixels, binary alpha; animation needs a paid plan) and DEC-054 (the 30° `top34_8` camera for every character
source).

## Problem Statement

The game makes characters by two routes (its DEC-012): 3D through Kiripix's character Recipe for the MC and authored
characters, and a 2D **sprite route** for NPCs and creatures: PixelLab PixFlux figures on a 56×56 canvas (~52 px people,
steered to the 30° view with an `init_image` from the `model` Stage's `still.png`), and AI images plus cleanup for creatures.
Its plan needs:

| Game milestone | Need | Frames |
|---|---|---|
| M02 ([0041](../../../urban-mystery-club/docs/backlog/m2/0041-m02-sanjay-sleeping-mc.md)) | Sanjay, idle in 4+ directions | PixelLab; a hand fit is an acceptable fallback |
| M04-10 | Raccoons in 4 facings, the wildlife-removal worker, Sanjay's battle frames | PixelLab or AI image; **the first real need** |
| M06-08 | Static witnesses | PixelLab, one frame |
| M08-06 | "Waiting Ones" enemies, 4 facings | AI image + cleanup, or a placeholder |

Kiripix has no Kind for this. `character` is 3D only (`model → rig → clips → render → …`), `prop` is one still frame with a
footprint, and `portrait` and `vfx` are Later. So today the game's main session fits these frames to the palette by hand and
makes normals with its own `tools/normal_map.py` (a "pillow" height from the alpha's distance to the edge, then Sobel). They
miss Kiripix's palette rules, its outline and the pivot drift check, and the game needs a second loader for them.

On PixelLab's free plan (DEC-044) a figure comes as one still per direction; animation needs a paid plan. So the near-term
frames are mostly **one-frame clips in 4 or 8 directions**, and imported animation is the less common case. The Kind must make
the one-frame case cheap and still take whole animations.

## Solution

A new Kind, `sprite`: an animated actor built from imported 2D frames. It ends where a character ends, so **from `palette`
down it is the character Recipe**, and its export is the character's, byte for byte in format.

**frames → fit → palette → finish → sheet → export**

| Stage | What it does | Owner input | Checks |
|---|---|---|---|
| **frames** | Cuts the imported sheets into `<clip>/<dir>/<NNN>` frames at source resolution. A sheet is a PNG with a grid (one row per direction, or one column) or a ZIP of frames per clip and direction, as PixelLab exports both. Directions are the character's compass names, `s sw w nw n ne e se` from the screen's view, `s` facing the camera; `directions` is `8`, `4` (`s e n w`) or `1` (`s`, a static figure). | Imports sheets; a `sheet` Decision maps a PNG's rows to directions; a `clip` Decision per clip (fps, loop, stationary) | `frames.direction_missing`, `frames.frame_count` (directions of one clip differ), `clips.bad_name`, `clips.duplicate_name` |
| **fit** | Per frame, onto the target pixel grid: `grid` (detect the pixel grid; PixelLab's 1:1 output gives scale 1) or `downscale` (AI images only), with one scale for the whole Asset so every frame is the same size. Optional chroma key first. Alpha binarised by vote. Measures each frame's **feet** and places every frame on one common cell around one pivot, with room for the outline. | `pivot` Decision (a click), only when the measured feet are wrong | `fit.grid_differs`, `fit.alpha_partial`, `fit.height` (info: the figure's height against `[character] height`) |
| **palette** | The character's `palette` Stage, unchanged: one subset of the Project palette across every frame (`colors`), dither, orphans. | — | `palette.off_palette` |
| **finish** | The character's `finish`: the outline in a palette colour after mapping (`outline`, `outline_colour`, `placement`), and normals, now from a choice: `pass` (the character's render pass), `height` (Sobel on a height from the alpha) or `flat`. | — | `normal.size_mismatch`, `palette.off_palette` |
| **sheet** | The character's `sheet`, unchanged: one atlas, one cell, the pivot at the feet. | — | `sheet.pivot_drift`, `sheet.frame_overflow`, `sheet.frame_count`, `sheet.empty_frame` |
| **export** | The character's `export` and Exporter: `color.png`, `normal.png`, `character.json` (schema 1), `texture.tres`, `frames.tres`, the `AnimatedSprite2D` scene. Animation names `<clip>_<dir>`, frozen once exported. | — | `export.no_target` |

## Decisions (made here; the Owner may overturn any)

**Reuse, not a copy.** The character's `palette`, `finish`, `sheet` and `export` all read one frame list, `render.json`
(`frame`, `pivot`, `directions`, `clips` with each frame's files and pivot), from the Stage named `render`. One refactor lets
them read it from a named Stage instead, and the sprite's `fit` writes the same document (with only a colour pass). Nothing
in their outputs changes for a character, so no character rebuilds.

**Import.** A sheet is a Source file, immutable once imported, like a Variant: `kiripix import <id> <file.png|file.zip>
--role sheet`, stored in `src/sheets/` by hash. Nothing is unpacked into `src/`; the `frames` Stage reads the file. A ZIP holds
only PNGs, and a path that leaves the archive, or a non-PNG, is refused at import.
- **A PNG sheet** needs a `sheet` Decision: the file, the clip, `layout` (`rows` or `columns`: one direction per row, or per
  column), the directions in that order, and the frame count; the cell is the sheet's size divided by those. A PixelLab
  rotation sheet is a one-frame clip.
- **A ZIP** is read by a naming rule: each PNG's path names a direction (PixelLab's `south`, `south-east`…, or our `s`, `se`…)
  and a frame number; the clip is the folder above the direction (PixelLab's animation name, made snake_case), or `idle` for
  a rotation with no animation. A `sheet` Decision may rename clips (`{"breathing-idle": "idle"}`). The exact PixelLab layout
  is confirmed on a real export first (the trial, [0175](0175-m4-sprite-pixellab-export-trial.md)).

**Directions: a missing one is a finding, never mirrored.** As for 3D (M3 Q6), so an asymmetric figure (a rake in one hand)
stays right. `frames.direction_missing` is an error naming the clip and direction, with an `owner_action` to import it. With
`directions = 1`, only `s` is expected. A 4-direction sprite exports four animations per clip; the game picks the nearest
(its loader's work, as it is for a missing clip).

**The pivot comes from the feet.** `fit` measures each frame's feet: the centre of the opaque pixels in the figure's lowest two
rows. One pivot per direction is the median of those over the direction's stationary frames (all its frames when no clip is
stationary), so the figure keeps its place on PixelLab's canvas and a walk's stride doesn't move the body. A `pivot` Decision
(per direction, or for all) overrides it with a click, for a figure with a shadow or a tail at its lowest row. The frame list
records both, `pivot` (used) and `feet` (measured), and `sheet.pivot_drift` reads `feet` when it's there: a stationary frame
whose feet stray from the pivot is reported, with the `fix` `kiripix set <id> fit align_feet=true`, which places each
stationary frame by its own feet. Off by default, so the source is kept unless the Owner asks.

**Fit.** `grid` is the default: PixelLab's output is pixel art already, and an exported ×2 or ×4 upscale is detected
(`detect_grid`). All frames must share one scale, or `fit.grid_differs` names the odd ones. `downscale` is for AI images: one
scale for the whole Asset, the one that brings the reference frame's figure (the first frame of `idle` in `s`, or the first
frame) to `height` (default the Project's `[character] height`, 52), with the line-keeping downscale and the alpha by vote, as
for a Prop. `chroma` (a `#RRGGBB`, off by default) keys a flat background first. Matting an AI image (BiRefNet) is Later; the
Owner removes the background before import.

**Outline.** The character's 1 px silhouette in a palette colour, after `palette`. `placement = edge` is the sprite's default:
a PixelLab figure has its own dark edge, and `edge` repaints exactly those pixels in the Project's outline colour, so a sprite's
line matches a character's colour and width without growing it to 2 px. `outside` is for a source with no line, and
`outline = false` keeps the source's own line as it is.

**Normals.** `height` by default: a rounded height from the alpha's distance to the edge, plus an optional share of the
pixels' lightness (`relief`, default 0), then Sobel, quantised to `normal_levels` and encoded exactly as the character's.
This is the game's `tools/normal_map.py` moved into Kiripix as two Ops, so the game's lighting looks the same and the tool can
go. `flat` writes (128, 128, 255), a figure lit evenly.

**Palette ramps per part** (M4's [0147](0147-m4-character-palette-ramps.md)) need a part label per pixel, which a sprite has no
material pass for. A hand-painted label image per frame is possible, but is **Later**: no sprite in the game's plan is
recoloured.

**The Kind's name is `sprite`.** Its IDs are `sprite.<name>` and it exports to `<root>/sprite/<name>/`. "Sprite" is also
Godot's `Sprite2D`, so code and messages say "a sprite Asset" or "the sprite Kind", never "a sprite" for a frame. The glossary
gains it.

## Where it goes

| Option | For | Against |
|---|---|---|
| **M4, after the palette ramps (0147): chosen 2026-11-12** | The game's first real need is its M04, which already waits for Kiripix M4 (the `area` Marker). Most of the Kind is reuse: about 0.8–1.2M tokens. Sanjay (game M02) can use it if it lands first. | M4 is already large (rooms, Looks, ramps, the M3 follow-ups). |
| M5, first | Keeps M4 to rooms and characters. | Raccoons (game M04) are fitted by hand, or are placeholders, as M04-10 allows. Sanjay too. |

Either way Sanjay (game M02) is fitted by hand, as the game's ticket 0041 already plans, unless this lands first. The trial
below uses that hand fit's PixelLab export, so the game's M02 work is the trial's data.

## User Stories

1. As the game, I want sprite actors in exactly the character's export format, so that one loader plays both routes.
2. As the Owner, I want to import a PixelLab sheet or ZIP as it comes, so that I never cut frames by hand.
3. As the Owner, I want a missing direction reported, not mirrored, so that an asymmetric figure is never flipped wrong.
4. As the Owner, I want sprites on the Project palette, with the same outline colour and width as rendered characters, so that
   NPCs and the MC look like one cast.
5. As the Owner, I want the pivot at the feet, found for me, with drift reported on stationary clips, so that an NPC stands where
   it's placed and doesn't swim.
6. As the game, I want a normal map for every frame, so that 2D lights light a sprite as they light a character.
7. As the Owner, I want one screen for the import and the frames I already know from characters, and a click for the pivot, so
   that a sprite takes minutes.

## Child tickets

Budgets in tokens.

| Ticket | What | Agent | Depends on | Budget |
|---|---|---|---|---|
| [0175](0175-m4-sprite-pixellab-export-trial.md) | Trial: a real PixelLab export (the game's Sanjay from its 0041) taken through by hand: the ZIP's layout, the figure's height and edge line, the feet, `height` vs `flat` normals in Godot | character-pipeline | the game's 0041 export | 30–60k |
| [0176](0176-m4-character-stages-read-a-named-frame-list.md) | The character's `palette`, `finish` and `sheet` read the frame list from a named Stage; `finish` gains `normals` (`pass`, `height`, `flat`); `sheet.pivot_drift` reads `feet` | character-pipeline | 0150 | 80–120k |
| [0177](0177-m4-sprite-ops.md) | Ops: `slice_grid`, `feet_point`, `height_from_alpha`, `normals_from_height` (spec §7), with goldens | imaging-engineer | — | 120–200k |
| [0178](0178-m4-import-a-sheet.md) | Core: `import --role sheet` (PNG or ZIP, refused when unsafe), `src/sheets/`, `show`, the contract | core-engineer | — | 100–150k |
| [0179](0179-m4-sprite-recipe.md) | The `sprite` Recipe: `frames` and `fit`, the `sheet`, `clip` and `pivot` Decisions and their Checks, the reused Stages wired in; the glossary and spec §6.4 | character-pipeline | 0175 to 0178 | 250–400k |
| [0180](0180-m4-export-a-sprite.md) | Export: the sprite through the character Exporter, its clip IDs frozen in the Manifest, `--prune` | godot-export | 0179 | 60–100k |
| [0181](0181-m4-ui-sprite-screens.md) | UI: import with `--role sheet`, the `sheet` and `clip` forms, the frame strip on `fit` to `sheet`, the pivot by a click | ui-engineer | 0179 | 120–200k |

**Total: about 0.76–1.23M tokens.** No gate ticket: the M4 gate ([0142](0142-m4-gate.md)) gains one line (a raccoon or Sanjay
in 4 directions, lit, in Godot beside a character), and the agent acceptance test is unchanged.

**The least screen work** ([0181](0181-m4-ui-sprite-screens.md)): no new screen. The import drop already takes a role (`ImportRole`); the frame strip
(`frameScreen.tsx`, ticket [0115](../m3/0115-m3-ui-frame-strip-and-player.md)) already reads `render.json`, so it shows `fit`,
`palette`, `finish` and `sheet` once it knows the sprite's Stage names; the `sheet` and `clip` Decisions are small forms; and the
pivot is one click on the frame strip, drawn as a cross, like a Prop's origin.

## Order

| Wave | Tickets |
|---|---|
| 1 | 0175 (no code), 0177 and 0178, side by side; 0176 once 0150 and 0168 are done |
| 2 | 0179 |
| 3 | 0180 and 0181, side by side |

**Don't run these at the same time, because they edit the same files:**
- 0176 and 0148, 0150 or 0168 (`character_palette.py`, `render.json`'s contract): 0176 goes after 0150 and 0168 (the ramp
  table).
- 0176 and 0159 (`sheet`'s Checks).
- 0177 and 0149 (`kiripix/ops/__init__.py`).
- 0180 and 0151 (`kiripix/export/`).
- 0181 and 0157 (`web/src/App.tsx`).

## Testing Decisions

- **CLI seam** for every Stage on small synthetic sheets committed as fixtures (a 4-direction PNG sheet, a ZIP in PixelLab's
  layout from the trial, an upscaled ×4 sheet, a sheet missing a direction). No Runner and no Blender, so no fakes are needed.
- **Golden seam** for the new Ops.
- The character's tests and goldens are unchanged by ticket 2: that is its acceptance.
- **Export** as text against a temporary Godot folder, as for characters; `character.json` compared with a character's by its
  schema.
- A new or changed Command has a sample in `tests/cli/test_contract.py`.

## Out of Scope

- Palette ramps per part for sprites (Later, above).
- Matting AI images (BiRefNet on frames): the Owner removes backgrounds first.
- Mirroring a direction, even as a Decision. If the game needs it, it's a new Decision, recorded and visible, never automatic.
- Generating frames (PixelLab through `gen`): M6's Providers.
- Animation authoring or in-betweening.
- Portraits and VFX sheets (Later).
