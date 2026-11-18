---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0243-m5-portrait-recipe.md]
---

# M5: UI: the portrait's screens

Spec §11. Part of [0240](0240-m5-portrait-kind.md). Built on the Commands of [0242](0242-m5-portrait-asset-and-emotions.md) and
[0243](0243-m5-portrait-recipe.md), with no logic of the UI's own.

## What to build

- **An emotion strip:** every emotion of the set as a thumbnail, with its pick, its status and its findings. Import and pick
  an emotion's Variant from it, as the Looks screen does.
- **Flip in place:** the selected emotion over the neutral at the canvas's size, toggled by a key, so the Owner sees anything
  that moves. `portrait.shimmer`'s boxes are drawn on it.
- **The `face` region:** drawn with the Looks' polygon and brush tools.
- `fit`, `palette` and `finish` reuse the Prop's screens where they can.

## Acceptance criteria

- [x] Playwright: on a built fixture portrait, the strip shows each emotion, a key flips it over the neutral, and a drawn
      `face` region is recorded as a Decision.
- [x] `npm run build` passes.

## Result

Built in `web/` on the Commands only (`decide`, `import`, `pick`, `run`, `show`, `check`, `describe`); no logic of the UI's own.

- **Emotion strip** (`portraitScreens.tsx`, `EmotionStrip`, on every portrait Stage): the neutral and each emotion as a thumbnail (the
  furthest built Stage's image, else its picked Variant; whole-number scale, never smoothed), its pick from `show.emotions` ("Variant
  x", "no image picked", "made on another Source") and its findings (those whose `data.emotion` names it). Declare an emotion (one
  `decide emotion` on `source`), and import an image for the selected emotion: one `import --emotion` then one `pick --emotion`, as
  the Looks screen does. On `source` the main area is the selected emotion's Variant grid; `1` to `9` pick, drops import.
- **Flip in place** (`PortraitPanel`, `portraitTool.ts`): `V` (or the buttons) lays the selected emotion over the neutral at the
  canvas's size, on every Stage after `source`; `1` to `9` pick the emotion, `0` the neutral. On `finish` the selected emotion's
  `portrait.shimmer` boxes (the finding's `data.boxes`) are drawn as red dashed boxes.
- **`face` region** on `register`: the Looks' brush, erase, polygon and erase-polygon tools (`MaskTool`; `B E G X`, `[ ]`), each
  gesture one `decide face` with `points`, and `radius` / `erase` where they apply, in the neutral cutout's pixels. By default
  `register` runs again after each edit (a toggle), so the region shown is `register/face.png`, which the Stage wrote. `Ctrl+Z` undoes.
- `cutout`, `fit`, `palette` and `finish` are the shared screens rendered from `describe`, as the Prop's are; no hand-written widget.
- Tests: `web/e2e/portrait.spec.ts` (4 flows, built fixture portrait): the strip, a key flips over the neutral (the pixels change
  inside the face only); a polygon and a brush stroke are `face` Decisions and undo steps back; shimmer boxes on `finish`; declare,
  import and pick from the strip. Screenshots: `web/shots/portrait-flip.png`, `portrait-face.png`, `portrait-finish.png`.

**Reads the UI had to work around (backend tickets):**
- `show`'s `outputs` lists only a Stage's top-level files, so an emotion's built image (`<stage>/emotions/<id>.png`) isn't listed.
  The UI builds the path from the Stage's `image` and learns whether it exists when it loads. `show` should give each emotion its
  built images per Stage, as `StateOut.images` does for a Prop's state.
- `portrait.emotion_unpicked` (a Stage's needs-input reason) has no `data.emotion`, so it can't be attached to one emotion's card;
  the strip shows the pick state from `show.emotions` instead, and the finding stays in the Stage's Checks.
