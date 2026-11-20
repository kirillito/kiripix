---
status: todo
milestone: M6
agent: imaging-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0332-m6-style-match-trial.md]
---

# M6: the style measures as Ops, and the `style.*` Checks

Spec §2 (principle 3), §7 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Every value marked
"set by 0332" comes from [the trial](0332-m6-style-match-trial.md); this ticket builds only the measures the trial kept.

## What to build

- **Ops** (`kiripix/ops/style.py`, pure: arrays in, numbers out, no I/O): one function per kept measure (set by 0332), each
  taking an RGBA image and what it needs (the palette, a normal image, the outline colour) and returning a small frozen
  dataclass of numbers. Nothing else in `ops` changes.
- **Checks** (`kiripix/checks/`, importing only `ops`): given an Asset's measures and its references' measures, a finding per
  measure out of range (set by 0332): `style.palette_use`, `style.value_range`, `style.saturation_range`,
  `style.outline_density`, `style.pixel_scale`, `style.light_direction`, for the kept ones only.
  - Each is a **warning** (the Owner's Q5 in 0324), naming the Asset's number, the references' range and the reference
    furthest from it.
  - Each has exactly one of `fix` or `owner_action`. A measure a parameter can fix (an outline off in `finish`, a sprite's
    `fit` scale) gives that `fix`; a painting's light gives an `owner_action`.
  - `style.measures`, an info finding, carries all the numbers, so `check --json` shows them even when nothing is wrong.
- The Stage each Kind is measured on is set by 0332 and lives with the Check, not in core.

Core's side (which Assets are references, reading their outputs, the cache) is [0334](0334-m6-style-references-and-wiring.md).

## Acceptance criteria

- [ ] Golden seam: each measure on small fixture images with known answers (a 2x-scaled figure, a figure with and without its
      outline, a shaded sphere lit from the left and from the right), exact numbers.
- [ ] Unit tests on the Checks: in range gives only `style.measures`; out of range gives the warning, its fix or owner action,
      and the numbers.
- [ ] `uv run lint-imports` passes: `ops` imports nothing else, `checks` only `ops`.
- [ ] Spec §7 lists the Ops and §6's tables the Checks per Kind.
