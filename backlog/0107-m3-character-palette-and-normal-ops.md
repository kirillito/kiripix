---
status: todo
milestone: M3
agent: imaging-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0094-m3-palette-stage-muddies-rooms.md]
---

# M3: Ops for a character's palette and its normal map

Spec §6.3 (palette, finish), §7 (colour, normals) and ADR 0004. Stories 10 and 12 of [0097](0097-m3-characters.md). Q9 of
0097 decides the palette subset: ask the Owner first. After [0094](0094-m3-palette-stage-muddies-rooms.md), so the
character uses the fixed mapping. Pure, numpy only, golden-tested, exported from `kiripix.ops`.

## What to build

- `palette_subset(frames, palette, n)`: the n palette colours that best fit every opaque pixel of all the frames together, in
  OKLab, ties broken by palette order. One subset for the whole character, so no frame maps to a colour another frame lacks.
- Mapping and orphan cleanup reuse the room's Ops; only transparent pixels stay transparent, and alpha stays binary.
- `quantise_normals(normal, levels)`: a normal pass quantised to its own levels per axis, never palette-mapped, renormalised.
- `encode_normals(normal)`: the normal as Godot 4.7 expects in a `CanvasTexture`'s normal map. State the axis convention in
  the docstring, with its source, so [0113](0113-m3-character-export.md) and the gate can check it.

## Acceptance criteria

- [ ] Golden tests for each Op, pixel-exact: a two-frame case where per-frame mapping would differ and the subset doesn't.
- [ ] `quantise_normals` at 1 level per axis and at 255 levels; transparent pixels stay (0, 0, 0, 0).
- [ ] `uv run lint-imports` passes.
