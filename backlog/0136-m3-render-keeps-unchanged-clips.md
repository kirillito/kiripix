---
status: todo
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0104-m3-render-stage.md]
---

# M3: `render` keeps the clips that didn't change

Spec §6.3 (render) and [ADR 0010](../docs/adr/0010-blender-renders-rebuild-and-are-not-pinned.md). Added 2026-11-08 for the game's
grid battles (its DEC-048): `attack`, `hit`, `ko`, `cast` and skill variants for five club members, in 4 or 8 directions. That's
about 12 clips x 8 directions x 8 frames, or roughly 770 frames per character. The `render` Stage's output is swapped in whole, so
adding one clip renders every clip again.

Not yet in 0097's wave table; it goes after 0104.

## What to build

- Each clip and direction's frames are keyed by what they're made from: the Model, the rig, that clip's own entry in
  `clips.json`, the camera preset, the render settings and the Blender version. On a rebuild, frames whose key matches are copied
  from the Stage's previous output instead of rendered. The new output is still swapped in whole, so the write stays atomic.
- If core gives a Stage no way to read its previous output, stop and say so: that hook is a `core-engineer` ticket of its own.
- Progress events and the run's result say how many clip and direction pairs were reused.

## Acceptance criteria

- [ ] CLI seam on the fake renderer: add a clip, and only its frames are rendered (the fake counts them). A camera change
      renders everything.
- [ ] The output is byte-equal to a full rebuild's.

Budget: 200–350k tokens.
