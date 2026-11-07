---
status: done
milestone: M2
agent: ui-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
depends_on: [0043-m2-layers-stage.md, 0044-m2-plate-from-difference.md]
---

# M2: the UI layers screen

Spec §11 (Layers and masks). Stories 1, 2, 5 and 6 of [0037](0037-m2-layers-and-props.md).

## What to build

- A hand-written screen in the masks screen's style, reusing its canvas and `CanvasTool`: click-to-segment with the
  `segment-preview` Probe on hover, shift-click subtracting, a Layer list with its ID field, toggles for each Layer, the Plate
  and the hole, and the `grow` parameter from `describe`.
- Each click is one `decide`. A `run --rerun` is the screen's primary action, shows progress, and can be cancelled. A
  `needs-review` Stage opens with a before and after, and Accept as its primary action.
- D1's trim gesture: one Command on release.
- `plate-import` by drag-and-drop or a file picker.
- The UI holds no logic: hole, grow and Plate all come from Command outputs.

## Acceptance criteria

- [x] Playwright with fake Runners: hover records nothing; a click records one Decision; the primary action leads to
      `needs-review`; Accept gives `done`, and the Layer can be toggled.
- [x] Playwright: `plate-import` gives Layers with no Runner call, and `done`.
- [x] Measured on a real room the way [0059](0059-m2-slow-click-to-segment.md) measured `masks`, and recorded in this
      ticket: the time from hover to preview on the layers screen, warm and straight after a rebuild.

## Notes

Built and passing
(`web/e2e/layers.spec.ts`, 4 flows; the rest of the suite passes except `place.spec.ts` "a y-sort line is drawn with a drag", below).

- The screen is `web/src/layerScreen.tsx`. It reuses `MaskTool` (click, Shift-click, brush as the trim stroke, hover through
  the Probe) and `PixelCanvas`, and adds a small `LayerView` canvas tool that draws each built `layer.<id>.png` and the Plate
  on or off. The hole is `foreground.png`, tinted. `grow` and `difference` come from the generic `describe` panel.
- Rebuild after a click is its own switch, **off** by default (a rebuild is a Runner call, and the Owner asked for `run --rerun`
  as the primary action); a trim and a `plate-import` still run the Stage straight after when it's on.
- On the Runner path a click goes to `needs-review` after `run --rerun`, and Accept gives `done`. On the `plate` path, no
  Runner is called (checked: no `runner-calls.jsonl`) and the Stage is `done`. A wrong-size Plate image shows `next`'s
  owner_action.
- **The hover preview comes from the `segment-preview` Probe, which is served by `masks`' hook** (`probes.py` takes the first
  Stage with a `segment` hook; `layers` has none). It is the segmentation of the Source mapped to the target: it does not
  include `grow`, and doesn't know the Layer ID. The Layer's final alpha therefore differs from the preview by the grow rim.
  A Probe that took the `layers` Stage's call would be a small backend change, if the Owner wants the preview to match. On the
  `plate` path there is no preview (no Runner), and the screen asks for none.
- `place.spec.ts` "a y-sort line is drawn with a drag" now fails: the `ysort` Marker needs a `layer` (0046/0047) and the place
  screen sends none. That is ticket 0054's, not touched here.

### Measurement (criterion 3)

No real room (`room.harbor_front`) and no GPU weights were available to the agent. Because the preview is the `masks` hook's,
the numbers should equal 0059's; the steps below confirm that on the layers screen. On the Owner's GPU, with `kiripix serve`
running and `room.harbor_front` open on the layers Stage:

1. Cold: restart `kiripix serve`; hover once over an object; time from the pointer stopping to the yellow preview (DevTools
   Performance, or the `data-preview` attribute on the canvas turning non-zero).
2. Warm: hover a second object; time to preview (median of 6).
3. Straight after a rebuild: click an object (rebuild on, or `run --rerun`), then hover another as soon as the Stage is
   `needs-review`; time to preview (median of 4). Also with a change that alters the Plate (a trim), because the embedding is
   keyed on the Source, which a layers rebuild doesn't change.
4. Record the three numbers here beside 0059's `masks` ones.

**Measured by the Owner, 2026-11-05**, `room.harbor_front` on the GPU, time from the hover to the preview:

| | layers screen | 0059's `masks`, GPU after |
|---|---:|---:|
| Cold server | 1.84 s | 6.22 s |
| Warm, repeat hover | 0.045-0.05 s | 0.07 s |
| Straight after a rebuild | 1.39 s | 0.08 s (1.20 s after a click with rebuild on) |
| After a trim | 1.20 s | - |

Warm hovers match `masks`. After a rebuild of `layers` the hover takes over a second: the rebuild calls LaMa, so the next
hover reloads SAM 2 and encodes again, like 0059's "hover straight after a click with rebuild on". Making `run --rerun` use
the warm Runner is [0064](0064-m2-rerun-on-the-warm-runner.md).
