---
status: todo
milestone: M3
agent: core-engineer
type: ticket
---

# M3: `preview` shows the Layers, and can brighten a dark room

Spec §10.5. Found by [0076](m2/0076-m2-claude-layers-first-pass-trial.md). `preview` can show the Plate and tint Masks, but not a Layer's
alpha, so nothing shows where a Layer's edge falls on the object. Claude drew it in a scratch script. These rooms were also too dark
to judge by eye, with mean luma 29 to 46 of 255, so the script brightened them 1.8×. Without that, r01's rails could barely be read.

## What to build

On `kiripix preview`, with `--region`, `--zoom` and `--grid` working as now:

- **`--overlay layers`:** the fit image with each Layer's alpha tinted, a different colour for each. `data` gives each Layer's colour,
  as `masks` lists the Masks today. It reads the `layers` output as built, including one awaiting review, and says when it's awaiting.
- **`--layer <id>`:** with that overlay, tint only that Layer. An unknown ID is an `input.invalid` that names the Layers.
- **`--brighten <factor>`:** multiply the image before the tint, clipped, for any Stage and overlay. Default 1, which changes nothing.
  It's for looking only: it's a new pure Op, and nothing but the preview file sees it.

The preview's file name carries the new options, so that previews don't overwrite each other.

This ticket adds no UI. The Owner reviewed r01 in the UI in the same dark conditions, so a brightness control on the canvas may be
worth its own ticket for `ui-engineer`.

## Acceptance criteria

- [ ] CLI seam: `--overlay layers` writes a file, and its pixels differ from the fit image exactly where a Layer has alpha.
- [ ] `--layer` tints that Layer only, and an unknown ID is refused with the Layers named.
- [ ] It works while `layers` is in `needs-review`, and says so.
- [ ] With no built Layers, the finding says so and names the fix.
- [ ] Golden seam: the brighten Op, including clipping, and a factor of 1 returns the image unchanged.
- [ ] `--brighten` changes no file outside `.kiripix/previews/`, and no status.
- [ ] `tests/cli/test_contract.py` still passes with the new options.
