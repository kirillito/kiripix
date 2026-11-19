---
status: done
milestone: M5
agent: ui-engineer
type: ticket
depends_on: [0298-m5-portrait-reads-and-face-review.md]
---

# M5: UI: what the 2026-11-18 review left in the portrait and Wearable screens

Left by the batch review of [0245](0245-m5-ui-portrait-screens.md), [0296](0296-m5-ui-read-gaps.md) and
[0297](0297-m5-review-follow-ups.md). Already done in the review: the walk test's Link reach reads `show.tile`, `picture` and
`gray` share one fetch-and-cache, and the emotion strip leaves the ID's rules to `decide`.

## What to do

- **`useWearables`** (`web/src/wearableScreens.tsx`): take a body's Wearables and their `order` from its `show`
  (`wearables`, 0296) instead of reading each Wearable's `sheet` parameter and `sheet.json`.
- **The emotion images:** read them from `show` (0298) and drop `emotionImage`'s path building.
- **The strip's status per Stage** for each emotion (0245 asks for "its status"; it shows only the pick).
- **`web/src/App.tsx`:** the `emotionShown ? … : stateShown ? … : show` cascade in `pick`, `importFiles`, `variants` and
  `gridShow`, and the rebuild cascade, into one helper each.
- **`IMAGE_STAGES`** in `web/src/portraitScreens.tsx` repeats the recipe's Stage order: read it from `show.stages`.

## Acceptance criteria

- [x] `npm run build`, `web/e2e/portrait.spec.ts` and `web/e2e/wearables.spec.ts` pass.

## Result

- `useWearables` reads each body's Wearables and `order` from the body's `show` (`wearables`); the Wearable's own `show` is still read for its `sheet.json` and `render.json` paths (the cost and the preview).
- `emotionImage(show, stage, id)` reads `show.emotions[].images` (0298); the path building is gone, and `ShowData.emotions[].images` is typed in `web/src/api.ts`.
- The strip shows, for each emotion, each Stage that holds an image of it, with the Stage's status (`emotion-<id>-stages`).
- `App.tsx`: `ownShown` and `ownTarget` replace the emotion/state cascades in `pick`, `importFiles`, `variants` and `gridShow`; `rebuildOn` replaces the rebuild cascade.
- `IMAGE_STAGES` is gone: the thumbnail reads `show.stages` in reverse.
- `npm run build` and both specs pass (run with `--workers=1` under load: with parallel workers on a busy machine three wearables tests timed out waiting for the Stage buttons, and passed alone).
