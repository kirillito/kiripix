---
status: todo
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0147-m4-character-palette-ramps.md
---

# M4: Ops and a Check for palette ramps per part

Spec §6.3 (palette) and §7. Part of [0147](0147-m4-character-palette-ramps.md). Ops are pure: numpy in, numpy out.

## What to build

In `kiripix/ops/character.py`, beside `palette_subset`:

- `part_ramps(frames, labels, parts, palette, steps, reserved)`: for each part (a set of material indexes in the `labels`
  images), the `steps[part]` palette colours that best fit that part's opaque pixels across all frames, in OKLab as
  `palette_subset` does, dark to light. No colour is in two ramps, nor in `reserved` (the fixed parts' subset, the outline
  colour). When two parts want the same colour, the one whose fit loses least takes the next-best colour. A part that can't get
  `steps` free colours raises an error naming the part.
- `quantize_by_part(frame, labels, ramps, fixed)`: each pixel mapped only onto its own part's ramp, or onto the fixed subset when
  its material isn't in a part. Ordered dithering, if on, stays inside a part's ramp.
- Orphan cleanup that keeps parts apart: an orphan pixel takes a neighbour's colour only from its own part. **An island that is
  all of its material's pixels there (it touches no pixel of the same material) is kept**, so the cleanup removes shading specks
  inside a material but never a detail that is a material of its own. Found on mc02 (2026-11-11): its eyes are 1 px each at
  52 px, and the default `orphan_size=1` painted them over with skin in all but 9 of 137 front frames. With `orphan_size=0`
  they show in 131, but about 30 shading specks a frame come back with them. This rule keeps the eyes and still cleans the
  specks.

In `kiripix/checks/`:

- `ramp_shared`: a finding `palette.ramp_shared` when a colour of one part's ramp appears in a pixel of another part, or in two
  ramps; the finding names both parts and the first pixel.

## Acceptance criteria

- [ ] Golden tests: two parts of near-identical colour get disjoint ramps; a part with a texture gets `steps` colours; an orphan
      pixel on a part boundary takes its own part's colour; a 1 px island of a material of its own (an eye) is kept, and a 1 px
      shading speck inside a material is cleaned.
- [ ] `palette_subset` and the room `palette` goldens are unchanged.
- [ ] `uv run lint-imports` passes.
