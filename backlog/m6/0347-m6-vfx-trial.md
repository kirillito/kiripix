---
status: todo
milestone: M6
agent: imaging-engineer
type: trial
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: trial: battle effects as sprite sheets, and where their frames come from

Spec §14 (Later until 2026-11-19: "VFX sheets (the game's battle skills and its M18)"). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Prototype code stays in `backlog/m6/0347-trial/` or the scratchpad,
not in `kiripix/`. The game's side: its M06 (`../urban-mystery-club/docs/backlog/m6/0062-m06-props-phases-boss.md`:
placeholder sparks, shake and landing), the Jazz Musician's sound attacks and buffs (M06-12), the Beast Master's summon
(M05-15), and its M18 (the Lady's VFX).

## The question

Battle effects in the game are placeholders. What does one effect need to look right beside the 52 px cast and the painted
rooms? Which route makes its frames at $0 and in the Owner's time? And how much of it does Kiripix already do?

## What to do

1. **The list:** with the game's M06 tickets, five effects that span the need: a hit spark (small, 4–6 frames), the Jazz
   Musician's sound wave (a cone of cells), the summon's puff, a buff's glow on a unit, and a telegraph on a target cell.
   Record each one's size, frames, and whether it's lit by the room's lights or glows (additive, unshaded).
2. **The hypothesis first:** an effect is a `sprite` (spec §6.4) with `directions=1`, no outline, `normals=flat`, and the
   Project palette or a few glow colours. Try it through the existing Commands. Note every gap: an outline it can't skip, a
   palette it shouldn't use, alpha that must stay partial for a glow, a pivot that isn't feet.
3. **Routes for the frames**, each on at least two effects:
   - (a) the image model's own UI: a strip of frames on a flat background, imported as a sheet;
   - (b) a kit hand-painted at target size, as a room Loop's kit is;
   - (c) Ops: frames made from one painted frame by whole-pixel Ops (scale, fade by palette steps, `shimmer`), as Loops do.
   A Blender route (particles at the characters' camera) is named, not tried, unless the Owner asks.
4. **In Godot:** each effect as an `AnimatedSprite2D` over a test room, with blend `add` and `mix`, lit and unlit. Capture a
   GIF of each beside a character.
5. **The Owner's view** on the GIFs: which route per kind of effect.

## Acceptance criteria

- [ ] The five effects, the routes tried, and the Owner's minutes per effect, in a table here.
- [ ] The verdict: the `sprite` Kind with parameters, or a `vfx` Kind of its own, with the reason.
- [ ] The build tickets filed, with `agent:` and `depends_on`, listed here and in 0324's order. Spec §14 says what M6 builds.
- [ ] The game told what to expect in its export (the files, the blend mode, the pivot).
