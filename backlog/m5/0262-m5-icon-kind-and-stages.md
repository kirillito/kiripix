---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0253-m5-icon-kind.md
---

# M5: the `icon` Kind and its Stages

Part of [0253](0253-m5-icon-kind.md), built on its recommendations: one Asset per icon, a Kind of its own, and no atlas. If
the Owner or the game's M08 overturns one, update this ticket before starting.

## What to build

- **The Kind:** `kiripix new icon <name>`, `describe icon`, and `[icon] size` (16, 24 or 32) in `kiripix.toml` (bump
  `schema_version`, with its migration).
- **`brief`:** `size` (the Project's unless set), `padding` (px, default 1, room for the outline), notes.
- **`source`, `cutout`, `palette`, `finish`:** the Prop's Stages, reused, not copied.
- **`fit`:** the Prop's `grid` or `downscale`, onto the square less the padding, centred. The alpha goes to the grid by vote.
  `fit.cropped` and `fit.padded` as the Prop's.
- **Checks:** `icon.size` (exactly the square), binary alpha, the palette.
- `export` is a stub until [0263](0263-m5-export-an-icon.md).

## Acceptance criteria

- [x] CLI seam: an icon from a fixture image on a flat chroma background builds through `finish` at 16 and at 32, centred,
      with binary alpha, every pixel on the palette.
- [x] A wrong size is `icon.size`. `new --help` lists `icon`.
- [x] Contract samples. The glossary's **Kind** lists `icon`. Spec §3 moves it out of "later", and spec §6 gets a short
      §6.6 Icon.

## Result

- `kiripix/recipes/icon.py`: the `icon` Kind (registered in `recipes/__init__.py`). `brief` has `size` (0 takes `[icon] size`), `padding`
  (default 1) and `notes`, with `brief.size_invalid` and `brief.padding_too_large`. `source` is the Prop's without states. `cutout`,
  `palette` and `finish` are the Prop's functions and parameters, imported. `fit` runs the Prop's `run_fit` onto the square less the
  padding and centres the result; `grid.json` is of the inner square and gains `inset` (the padding), so a click on the icon maps
  through the Grid after subtracting it. Checks: `icon.size`, `fit.padded`, `fit.cropped`, `image.partial_alpha`, the palette's.
  `export` is a stub: needs-input without a Godot project, and fails with a message naming 0263 otherwise.
- `[icon] size` (16, 24 or 32, default 24) in `kiripix.toml`: `schema_version` 7 to 8, migration `_add_icon_section`, the template
  updated. No new Command: `new` and `describe` read the Kinds, so `icon` appears in `new --help` and `describe icon`.
- Glossary Kind, spec §3, the spec's `kiripix.toml` example and new §6.6.
- A grid output larger than the square is left as it is, and `icon.size` names it, with `fit mode=downscale` as the fix.
- Tests: `tests/cli/test_icon.py`; the two tests that named schema version 7 now say 8.

## After review (2026-11-17)

Contract sample added: `test_contract.py::test_an_icon_validates` (`new icon`, `describe icon`, `show`).
