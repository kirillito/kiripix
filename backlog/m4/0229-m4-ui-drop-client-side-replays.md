---
status: done
milestone: M4
agent: ui-engineer
type: ticket
depends_on: [0228-m4-show-decisions-as-the-stage-reads-them.md]
---

# M4: UI: the loops and clips screens read `show`'s view, and replay nothing

Spec §11; ADR 0007 (adapters hold no logic). The UI side of [0228](0228-m4-show-decisions-as-the-stage-reads-them.md). Found
in the review of [0210](0210-m4-ui-loops-screen-follow-ups.md) and [0227](0227-m4-ui-a-character-made-from-a-base.md),
2026-11-15.

## What to build

- **Loops screen:** list the Loops from `show`'s Decisions as the Stage reads them. Remove `withEdits` from
  `web/src/loopScreen.tsx`. Undo and redo keep using the recorded list.
- **Clips screen:** list the clips from the same view. Remove the client replay of `remove` (the `latest` map in
  `web/src/characterScreens.tsx`).
- **Clip sources:** mark the base's from `clip_sources[].from_base`. Remove the folder-path guess (`ownFolder` and `fromBase`).
- While here, from the same review:
  - The rig screen shows `rig.base_mismatch` from its finding (code and bones), not from the failure's reason text.
  - Add a Playwright test for an inline `export.id_frozen` refusal on rename (0210 left it untested).
  - In the 0209 difference test, compare the previewed region with the built Look's region pixel by pixel, not only by
    count.

## Acceptance criteria

- [x] `web/src` has no replay of `remove` or `rename` and no path test for the base's files (grep finds no `withEdits`,
      `ownFolder`).
- [x] `loops-follow-ups.spec.ts`, `character-base.spec.ts` and `looks-follow-ups.spec.ts` pass, with the tests added above.
- [x] `npm run build` passes.

Budget: 40–80k tokens.
