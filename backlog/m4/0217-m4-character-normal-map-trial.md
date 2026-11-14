---
status: todo
milestone: M4
agent: character-pipeline
type: trial
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0213-m4-render-cel-band-edge.md, 0215-m4-finish-inner-lines.md]
---

# M4: trial: how strongly a character's normal map should light it in Godot

Spec §1 (a Sea of Stars-like look) and §6.3 (finish: the normal pass). Left over from the trial
[0160](0160-m4-flatter-character-look-trial.md), 2026-11-13. The Owner chose the shading and the inner lines
([0213](0213-m4-render-cel-band-edge.md), [0215](0215-m4-finish-inner-lines.md)) and wants to deal with the normal map
afterward, in Godot first.

In 0160's Godot capture (idle frame, one `PointLight2D`, mc03 male, normals flattened toward the camera) a full-strength
normal map lights each pixel by its facing, so a lit figure reads as a shaded solid beside a flat painted room. At 0.5 the
side toward the light stayed brighter without the bright specks. At 0 the light only tinted the figure. The rooms are never
re-lit (the game's lighting option A), so the figure should not look more 3D than the room it stands in. That capture
flattened the finished normal pass in numpy, outside Kiripix, and did not use the new look.

## What to find out

On the new look (`band_edge=0.62`, `band_smooth=1.5`, `inner_lines=dark`, from 0213 and 0215), on the mc03 bodies:

1. **Where to flatten the normal.** Three places, each rendered and captured the same way:
   - **In the game:** the `CanvasTexture`'s own normal map unchanged, and a lower light `height` or a lower energy on the
     `PointLight2D`, or a `normal_strength` on the sprite's material. Costs Kiripix nothing.
   - **In `finish`:** a `normal_strength` parameter that lerps each normal toward `(0, 0, 1)` and renormalises, as the 0160
     capture did. Needs a ticket and changes the exported `normal.png`.
   - **In `render`:** the same on the normal pass, so `depth` and the others are unaffected.
2. **What strength.** 1, 0.75, 0.5, 0.25 and 0, under the lights of 0160 (left, right, a lamp in the middle) and under the
   game's own lights if there is a room with one.
3. **Whether the lit side still tells the direction.** At low strength the light should still brighten the side it comes from
   in all 8 directions, and not wash the figure out.
4. **Whether it holds in motion.** Walk and attack, not only the idle frame. A normal that flickers between frames shows here.
5. **Whether `normal_levels` matters.** Today the pass is quantised to 8 values per axis. Try 4 and 16 at the chosen strength.

## How

- Reuse `C:\Homespace\urban-mystery-club-art\.kiripix\trials\0160-flat\` (gitignored): `godot/capture.gd`, `godot.py` and the
  variants. Add the new look as a variant, and capture walk and attack frames as well as idle.
- The game's own scene, `res://art/kiripix/character/<name>/<name>.tscn`, is the thing that ships: capture it as the game
  builds it where it differs from the trial's `Sprite2D`, so a light setting found here works there.
- Sheets at 5x with the strength and the light in each caption, not 1x.

## What to record, in this ticket

- The sheets and captures, with their paths.
- The Owner's choice: where the strength lives (game, `finish`, or `render`) and its default. If it is `finish` or `render`,
  a ticket to build the parameter. If it is the game, a note for the game's repo with the light settings.

## Acceptance criteria

- [ ] The sheets and captures above, their paths listed here.
- [ ] The Owner's choice recorded, and the build ticket filed or the game's note written.
