---
status: todo
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

- [ ] CLI seam: after two `import --look` calls and one `pick --look`, `show --json` lists both Variants and the pick.
- [ ] CLI seam: the Probe's region for a box equals, pixel for pixel, the region the `looks` Stage builds from a
      `difference` Decision with the same box and tolerance.
- [ ] CLI seam: the Probe on a Look with no pick exits 1 with a `fix`.
- [ ] Contract samples (the `show` output's schema, the Probe); `lint-imports` and `mypy` pass.

Budget: 80–140k tokens.
