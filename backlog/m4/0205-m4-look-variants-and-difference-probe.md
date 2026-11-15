---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0127-m4-room-looks.md
depends_on: [0130-m4-looks-stage.md, 0129-m4-look-variants.md]
---

# M4: list a Look's edit Variants, and a Probe that previews a `difference`

Found by [0132](0132-m4-ui-looks-screen.md) (2026-11-13), its gaps 1 and 2. Spec §6.1 (Looks) and §10.5 (`show`, `probe`).

## What to build

- **`show <id>`** on a room gains `looks`: for each Look with a stored edit, its Variants (name and file, as for the
  Source's) and the picked one, or `null`. This lets the looks screen offer an older edit, and lets an agent see what
  `import --look` stored.
- **The Probe `look-difference`:** args are a Look, then `x0,y0,x1,y1`, then an optional tolerance and an optional specks
  count, with the `difference` Decision's defaults. It answers with the region that Decision would add, as a Mask answer
  (`runs`, `pixels`, `box`; `--summary` leaves out the runs). It records nothing.
- It calls the same code as the `looks` Stage (`kiripix/recipes/regions.py` and the Ops in `kiripix/ops/looks.py`): the
  picked edit, registered and fitted, measured before the palette, with specks removed. So the answer can't differ from the
  build. A Look with no picked edit, or a room whose `fit` isn't built, is refused with a `fix` (`pick --look`, or `run`).

## Acceptance criteria

- [x] CLI seam: after two `import --look` calls and one `pick --look`, `show --json` lists both Variants and the pick.
- [x] CLI seam: the Probe's region for a box equals, pixel for pixel, the region the `looks` Stage builds from a
      `difference` Decision with the same box and tolerance.
- [x] CLI seam: the Probe on a Look with no pick exits 1 with a `fix`.
- [x] Contract samples (the `show` output's schema, the Probe); `lint-imports` and `mypy` pass.

Budget: 80–140k tokens.

## Result (2026-11-14)

- `show` on a room gains `looks`: for each Look with a stored edit, `look`, `variants` (name, file, `imported_as`, size, as for the
  Source's) and `picked` (null without a Pick). The Pick comes from the `looks` Stage's current Decisions
  (`sources.picked_look_edits`); the list from `src/looks/<look>/` (`sources.looks_with_edits`).
- The Probe `look-difference <asset> <look> x0,y0,x1,y1 [tolerance] [specks]` answers with a Mask answer (`runs`, `pixels`, `box`;
  `--summary` leaves out the runs), with the `difference` Decision's defaults. Work in `kiripix/core/look_probe.py`.
- One code path with the Stage: `recipes/looks.py` gains `fitted_look` (the edit registered, fitted and regraded, before the
  palette), which `_build_look` now calls too; the Probe then calls `difference_region` as `paint_region` does. A Look with no
  Pick is refused with `probe.look_not_picked` (`fix`: `pick`); a room whose `looks` inputs aren't built, with `probe.not_ready`
  (`fix`: `run`); a box outside the Plate, with `input.invalid`.
- Tests: `tests/cli/test_look_variants_probe.py` (7), including the pixel-for-pixel match with the built Look. The contract test
  already covers `show`'s output schema (it validates the new field) and the `probe` Command.
