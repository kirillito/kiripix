---
status: todo
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

- [ ] `npm run build`, `web/e2e/portrait.spec.ts` and `web/e2e/wearables.spec.ts` pass.
