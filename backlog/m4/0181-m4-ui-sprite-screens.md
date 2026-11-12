---
status: done
milestone: M4
agent: ui-engineer
type: ticket
parent: 0174-m4-sprite-kind.md
depends_on: [0179-m4-sprite-recipe.md]
---

# M4: the UI for a sprite: import, the frame strip, the pivot

Spec §11. Part of [0174](0174-m4-sprite-kind.md). **No new screen:** everything here extends one that exists. Every action is
one Command.

## What to build

- **`frames`:** the import drop with `ImportRole` `sheet` (PNG or ZIP); the imported sheets listed with their names; for a PNG
  with no `sheet` Decision, a small form (clip, rows or columns, the directions in order, the frame count) that is one `decide`.
  The `clip` Decision's form (fps, loop, stationary) is the character's clips screen form where it fits; otherwise a form from
  `describe`. `frames.direction_missing` shows as a finding a person can read (ticket 0093's style).
- **`fit`, `palette`, `finish`, `sheet`:** the frame strip, onion skin, direction picker and clip player of `frameScreen.tsx`
  ([0115](../m3/0115-m3-ui-frame-strip-and-player.md)), for a sprite's Stage names. The direction picker greys out the
  directions a 4- or 1-direction sprite doesn't have.
- **The pivot:** on `fit`, the pivot drawn as a cross on the frame; a click sets it (one `pivot` `decide`, for the chosen
  direction, or all with a modifier key); `Ctrl+Z` undoes it. A `sheet.pivot_drift` finding jumps to its frame, as it does for a
  character.

## Acceptance criteria

- [x] Playwright, on the synthetic fixtures: drop a ZIP and see its frames on `fit`; drop a PNG sheet, fill the form, see the
      frames; click a pivot and see it move; step a clip and switch directions by key.
- [x] No canvas smoothing; zoom stays integer.
- [x] `npm run build` passes.

Budget: 120–200k tokens.

## Notes

2026-11-12 (ui-engineer):

- No Command was missing. `show` already lists a sprite's `sheets` (with `png_count`), `import --role sheet` and the `sheet`, `clip` and
  `pivot` Decisions are all there. The UI adds `web/src/spriteScreens.tsx` (the `frames` screen) and extends `frameScreen.tsx`.
- `frames`: the drop (`.png`, `.zip`), the sheets listed by their imported name, a form for each PNG with no `sheet` Decision (one
  `decide`; it can be reopened with "change", and deciding a sheet again replaces it), a `clip` form (hand-written, one `decide` each;
  the character's clips form is built on Blender actions and sources, so it doesn't fit) and a table of the built clips. The form's
  checks (name pattern from `describe`, Directions from the compass, frames >= 1) only stop a request the schema would refuse; the
  Stage's Checks (`frames.direction_missing` and the rest) show in the Stage panel as for every Stage.
- A ZIP's clips can't be renamed in the UI (the `clips` map of the `sheet` Decision): the naming rule is provisional until 0175.
- `fit`, `palette`, `finish`, `sheet` use `FrameScreen`; `fit` joins `FRAME_STAGES` (a character has no Stage of that name). The
  direction picker greys out what `render.json` doesn't list, so a 4- or 1-direction sprite shows only its own. A `sheet.pivot_drift`
  finding jumps to its frame as it does for a character.
- The pivot: drawn as a cross at the cell's pivot. A click is one `pivot` `decide` for the shown Direction, Shift-click one for all.
  The Decision is in the fitted frame's pixels, not the cell's, so the click is shifted by (the direction's pivot in `fit.json` minus
  the cell's pivot in `render.json`). After the `decide`, `fit` is run again at once (a `run` of that Stage, no Runner), as a Mask
  edit does under ADR 0006, so the frame shows it; `Ctrl+Z` is `undo` followed by the same run. The cross therefore stays at the cell's
  pivot and the figure moves under it.
- Open: Shift-click sends the same x, y for every Direction (the Decision has no per-Direction offset), so it is right when the
  figures stand alike; with `align_feet` a stationary clip's frame is placed by its own feet and the click is read against the
  Direction's pivot, not that frame's. A Decision's `on_image` is false, so the pivot is not drawn from the Decision itself.
- Tests: `web/e2e/sprite.spec.ts` (5 flows, a real `kiripix serve`, a ZIP built in the test with stored entries).
