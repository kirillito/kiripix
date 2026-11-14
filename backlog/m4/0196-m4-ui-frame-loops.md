---
status: done
milestone: M4
agent: ui-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0191-m4-ui-loops-screen.md, 0192-m4-frame-ops.md, 0193-m4-loop-kit-and-import.md, 0194-m4-loops-build-imported-frames.md]
---

# M4: frame Loops on the loops screen

Part of [0183](0183-m4-ambient-animation.md), route (c). Spec §11. It extends 0191's screen and preview.

## What to build

- **Source choice** for a `frames` Loop: Op, kit or edits (edits hidden if 0193's Part B was cut).
- **Op:** choose `sway`, `shimmer` or `scroll` and set its parameters with sliders. For `sway`, click the anchor row on the
  canvas. The preview updates as the sliders move. On a Plate Loop, `sway` is disabled with `loop.no_fill`'s message and a
  link to the layers screen.
- **Kit:** "Write kit" runs `loop kit` to a folder the Owner picks, then shows its path; "Import frames" takes the painted PNGs
  (file picker or drop).
- **Edits** (Part B): per frame, import and pick a Variant, as on the looks screen.
- **Frame strip:** the frames as thumbnails at ×4 nearest, frame 0 marked as the room's; click one to show it alone in the
  canvas, with onion skin of the previous frame at low opacity. Findings per frame (`loop.drift`, `loop.misaligned`,
  `loop.flicker`, `loop.outside_region`) are badges on the thumbnail.
- **Timing** per frame: a ticks field under each thumbnail, besides 0191's even timing and `pingpong`.

## Acceptance criteria

- [x] Playwright against `kiripix serve`: a `sway` Loop on a Layer from the sliders; the preview plays and `loops.json` has
      it.
- [x] Playwright: write a kit, import two frames from fixture PNGs, set a per-frame tick count; the strip shows them with a
      finding badge on the stray one.
- [ ] The Owner makes the kitchen's frame Loop in the time 0184 measured or less, timed and recorded here.

Budget: 150–250k tokens.

## Result (2026-11-13)

Edits (Part B) are hidden: 0193 and 0194 cut it until trial 0184 has run, so the source choice is Op or Kit, with a hint saying Edits wait.

- **Screen:** `web/src/loopScreen.tsx`, `loopTool.ts`, `App.tsx` (`writeKit`, `importFrames`, `onStage`), `styles.css`. A `loop-form` select
  (colour cycle or frames; also on New Loop); the Cycle section shows only for `cycle`; Timing and the strip for both.
  **Op:** `sway` / `shimmer` / `scroll` buttons and sliders (committed on release as one `frames` Decision with every parameter, so two quick
  changes don't lose one); `sway`'s anchor row by the Anchor row tool (`R`, a line on the canvas); `sway` on the plate is disabled with
  `loop.no_fill`'s wording and a button to the layers screen. The preview rebuilds after each Decision (the screen's "rebuild" box).
  **Kit:** a folder field (on the server's machine), frame count, "Write kit" (`loop kit`, then its path shows), "Import frames"
  (`import --loop`, frame_001 onward read from that folder). **Strip:** thumbnails at x4 nearest, frame 0 marked "the room's", a click
  shows that frame alone with the previous one at 30 % (`data-loop-inspect`), a ticks field under each (one `timing` Decision with a
  list), badges for `loop.drift`, `misaligned`, `flicker`, `outside_region`, `off_palette`, `partial_alpha` (kit frames matched by
  `position.file`, others by "frame N" in the message).
- **Tests:** `web/e2e/loops.spec.ts`: sway from sliders and anchor row, the preview plays, `loops.json` has it; sway disabled on the plate
  with the link; kit written, two frames imported, a per-frame tick count, the badge on the stray frame. The Owner's timed kitchen run
  stays unchecked.
- **Backend gaps:** `import --loop` over REST takes a JSON list of server paths, and multipart one `file`: the browser can't upload several
  PNGs (no file picker or drop), so the Owner paints in the kit folder and the UI reads it from there. Multipart with several `file`
  parts would fix it. `loop.drift`, `loop.misaligned` and `loop.flicker` exist only with Edits, so no badge for them is tested.

## Closing notes (2026-11-13)

- Closed 2026-11-13; the Owner's timed kitchen run stays open, as in 0191.

## After trial 0184 (2026-11-14)

Part B is kept: the Edits source moves to [0221](0221-m4-ui-loop-edits-source.md).
