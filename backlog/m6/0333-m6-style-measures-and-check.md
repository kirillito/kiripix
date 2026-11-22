---
status: done
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

- [x] Golden seam: each measure on small fixture images with known answers (a 2x-scaled figure, a figure with and without its
      outline, a shaded sphere lit from the left and from the right), exact numbers.
- [x] Unit tests on the Checks: in range gives only `style.measures`; out of range gives the warning, its fix or owner action,
      and the numbers.
- [x] `uv run lint-imports` passes: `ops` imports nothing else, `checks` only `ops`.
- [x] Spec §7 lists the Ops (the Checks per Kind in §6's tables are 0334's, with the wiring).

## Result (2026-11-20, imaging-engineer)

Built the two measures the Owner kept in [0332](0332-m6-style-match-trial.md) ("The Owner's verdict"), and the `style.measures`
info finding. **Not built, as dropped by the Owner:** `style.palette_use`, `style.value_range`, `style.saturation_range`,
`style.light_direction` (a settings Check on `light_angle` is [0361](0361-m6-light-angle-consistency.md)). No Stage's output
changed, so no `version` bump.

**Ops** (`kiripix/ops/style.py`, exported from `kiripix.ops`), both take an RGBA uint8 array, opaque = alpha > 0:
- `outline_density(image, outline_rgb: tuple[int, int, int]) -> OutlineMeasure(outline_px, edge_px, density)`. The edge is an
  opaque pixel with a non-opaque 4-neighbour (the image border counts as non-opaque); `density` is 0.0 with no edge. For a
  character and a sprite, on `finish`'s colour frame. Not a Wearable: its `finish` draws no outline (the Owner, 2026-11-20, correcting 0332's first verdict); `OUTLINE_KINDS` was narrowed to match in the main session.
- `pixel_scale(image) -> ScaleMeasure(runs, gcd, median, run1_share)`: runs of one RGB colour among opaque pixels along every
  row and column (vectorised; checked against a plain loop on random images). Pass the image cut to its opaque box. For every
  Kind: `finish`'s colour frame for figures, `palette`'s Plate for rooms, a Prop's export.

**Checks** (`kiripix/checks/style.py`, exported from `kiripix.checks`; `Mapping` keys are Asset ids, the caller picks the
references; ties for "furthest" go to the lowest id):
- `check_outline_density(asset, measure, references: Mapping[str, OutlineMeasure], fix: str)`: a warning `style.outline_density`
  below density 0.5 (`OUTLINE_DENSITY_FLOOR`); nothing when the image has no edge. `fix` is the command that turns the outline
  on in `finish`. Position: the Asset, Stage `finish`.
- `check_pixel_scale(asset, measure, references: Mapping[str, ScaleMeasure], fix: str, stage: str | None = None)`: a warning
  `style.pixel_scale` at gcd >= 2 over >= 50 runs (`PIXEL_SCALE_GCD`, `PIXEL_SCALE_MIN_RUNS`). `fix` is the sprite's `fit`
  size or the room's re-source command; `stage` says which Stage's image was measured.
- `check_style_measures(asset, outline: OutlineMeasure | None, scale, fix)`: info `style.measures`, `outline` None for a Kind
  without the measure (rooms, props). `fix` is the command that shows the numbers again (an info finding still needs one).
- Each warning's message names the Asset's number, the references' range ("no references" when empty) and the furthest one;
  `data` carries the numbers (`density`/`gcd`, `references_low`, `references_high`, `furthest`, ...); `style.measures`' `data`
  has `outline_density` and `pixel_scale` objects.

Tests: `tests/golden/test_style_ops.py` (exact numbers on small fixed figures: outlined, without, half, 2x, 3x; no PNGs, since
the measures return numbers) and `tests/golden/test_style_checks.py`. `lint-imports` and `mypy` pass.
