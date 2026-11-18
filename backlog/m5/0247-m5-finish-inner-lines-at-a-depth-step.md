---
status: done
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0246-m5-inner-lines-at-a-depth-step-op.md]
---

# M5: `finish` draws inner lines where a part crosses itself

Spec §6.3 (finish). Part of [0236](0236-m5-the-games-next-needs.md), item 13. Uses the Op of
[0246](0246-m5-inner-lines-at-a-depth-step-op.md).

## What to build

- **`finish line_depth=<px>`** (float, default 0, meaning off): with `inner_lines` on, also draw a line inside one material
  where the depth steps by more than this many pixels of the render's scale. The Stage converts pixels to the depth pass's
  units from `render.json` (the camera's scale), so the setting means the same at any `height`.
- The colour is the material's line colour, as for a border (`dark`: the part's line step with `part_lines`; `outline`: the
  outline colour).
- The eye materials and the stamped eyes are untouched, as now. `line_skip`'s single names skip a material's depth lines too.
- `finish.json` records `line_depth`. Bump `FINISH_SCHEMA_VERSION`. At 0 the frames are byte-equal to today's.

## The Owner's check

On the art repo's `chargen` cast, with the split sleeves and trouser legs merged back into one material for two or three
characters: the cast sheet ([0226](../m4/0226-m4-cast-sheet-probe.md)) at `line_depth` 0, 1.5 and 3, next to today's split
materials. Record the Owner's choice of default, and whether `chargen` can stop splitting materials.

Prepared (rows top to bottom: `split_today`, `merged_0`, `merged_1_5`, `merged_3`; characters `mc03_male_clothes01`, `npc_elder_coat`,
`npc_mc_m_a`; scale 3), in [0247-check/](0247-check/):
- [sheet1_idle_s.png](0247-check/sheet1_idle_s.png): idle, south. Open this one first.
- [sheet3_walk_se_e_ne.png](0247-check/sheet3_walk_se_e_ne.png): walk, se, e, ne, 2 frames.
- [sheet2_idle_walk_5dirs_2frames.png](0247-check/sheet2_idle_walk_5dirs_2frames.png): idle and walk, s/se/e/ne/n, 2 frames (very wide).
Built in a scratch copy of the art Project, with `CHARGEN_MERGE=1` in the copy's `chargen/generate.py` (sleeve and hood into top,
bottom_r into bottom). Not applied to the art repo. The Owner, 2026-11-17: `split_today` looks the best. The default stays `line_depth` 0 (off), and `chargen` keeps
splitting materials; `CHARGEN_MERGE` is not ported to the art repo. `line_depth` stays as an option for a Model whose
materials can't be split. (Caveat on the sheets: the merged rows were rebuilt with `render.band_smooth` 0.0, today's
row has it mixed, so their shading differs too.)

## Acceptance criteria

- [x] CLI seam: on the fake Blender, with a depth step inside one material, `line_depth` above 0 puts a line pixel there in
      the line colour, and 0 is byte-equal to a run without the parameter.
- [x] The Owner's check above, with the sheet's path and the chosen default recorded here.
- [x] Spec §6.3 (finish) describes `line_depth`. `uv run lint-imports` and `uv run mypy` pass.

## Result

`finish line_depth=<px>` (float, default 0 = off) passes `depth_step` to the `inner_lines` Op: px / `px_per_unit` / (`far` - `near`)
x 65535, from `render.json`. `finish.json`'s `inner_lines` records `line_depth`; `FINISH_SCHEMA_VERSION` is 3. The fake Blender
gained `blender-depth-step` (a 16 bit depth with a step at the frame's middle). Test:
`tests/cli/test_character_inner_lines.py::test_line_depth_draws_a_line_inside_one_material_at_a_depth_step`.

Version: `FINISH_SCHEMA_VERSION` (now 3) is only written into `finish.json`, not hashed, so it does not make `finish` stale. The
`finish` StageSpec's `version` is bumped to 2 instead (ticket 0278): `finish` is stale on every character, a deliberate rebuild
(13 characters in the art Project). Tests also cover `line_depth=0` byte-equal to never set, and `dark` with `part_lines` drawing the
depth line in the part's first ramp step.

Left for the Owner: the cast-sheet check at `line_depth` 0, 1.5 and 3, the chosen default, and whether `chargen` can stop
splitting materials.
