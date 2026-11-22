---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0332-m6-style-match-trial.md]
---

# M6: a Project check that every character is lit from the same `light_angle`

Spec §6.3 (`render`'s camera preset) and §14 (M6). From the Owner's verdict on [0332](0332-m6-style-match-trial.md)
(2026-11-20): light direction can't be measured on a painting, and on a rendered figure the lightness follows the material, so
the style Check doesn't measure it. A figure's light is its render preset's `light_angle`; a setting can be compared directly.

## What to build

- A Project check (run by `check --all` and `export --all`, as `clips.timing_differs` is): `style.light_angle_differs`
  (warning) names each character, Wearable or base whose resolved `render` light angle differs from the Project's most common
  one, with its `fix` (the `set` that matches it) or an `owner_action` when the Project has no majority.
- Wearables follow their body's render, so a Wearable differs only through its body; say so rather than report it twice.

## Acceptance criteria

- [x] CLI seam: two test characters with the same angle raise nothing; a third with another raises the warning with its `fix`.
- [x] Spec §6.3's Checks list it.

## Result

`style.light_angle_differs` (warning) is a Project check in `kiripix/core/lightangle.py`, registered in `project_checks.py` (so
`check --all`, the queue and `district` run it) and called by `export --all` as a warning, narrowed by `--match` as
`clips.timing_differs` is. It compares each character's resolved `render` `camera` preset (the base's value included) by its
`light_angle` against the Project's most common angle. A character that differs gets the `fix` `kiripix set <id> render
camera=<a preset with the common angle>`; with no strict majority every character gets an `owner_action`. A Wearable is not
reported: its body's finding names it ("its Wearables ... follow its render"). A character whose preset doesn't exist is left to
`render.camera_unknown`. No Stage changed, so no `version` bump. Tests: `tests/cli/test_light_angle.py`. Spec §6.3's Checks list
has it.

Follow-up in the same batch: `test_export_all_carries_the_warning_and_still_exports` covers `export --all` (a built, exportable
character and an unbuilt one lit from another angle; with `--match` the hero's warning is kept and the export goes ahead).
