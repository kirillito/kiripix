---
status: done
milestone: M4
agent: ui-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0206-m4-loops-hold-one-loop.md, 0207-m4-rename-and-remove-a-loop.md, 0208-m4-import-several-frames-over-rest.md]
---

# M4: the loops screen: rename, remove, held Loops, and several frames at once

Follows [0191](0191-m4-ui-loops-screen.md) and [0196](0196-m4-ui-frame-loops.md). Spec §11.

## What to build

- **The list:** rename and remove, each one Decision (0207), so `undo` works. An `export.id_frozen` refusal shows inline,
  with its message.
- **Held Loops (0206):** a held Loop's region is drawn from its `region.png` as soon as it is built, with its `loop.held`
  finding inline. The preview plays the other Loops. Accept stays disabled while any Loop is held.
- **Import frames:** by file picker or by dropping several PNGs (and the kit's `kit.json`) on the strip, in one multipart
  `import --loop` (0208). The kit-folder route stays for the Owner who paints in place.

## Acceptance criteria

- [x] Playwright against `kiripix serve`: flood a region on a new Loop before picking any colour. The region shows, and a
      second, complete Loop plays in the preview.
- [x] Playwright: rename a Loop, then remove another; `loops.json` matches; `undo` restores the removed one.
- [x] Playwright: drop two fixture frames and `kit.json` on the strip; both show as thumbnails.

Budget: 100–180k tokens.

## Result (2026-11-15)

- **Rename and remove:** the selected Loop has a rename field and a Remove button, each one `decide` (`rename`, `remove`); Ctrl+Z is
  `undo`. A refusal (`export.id_frozen`, `loop.id_taken`, `loop.unknown`, `loop.rename_same`) shows beside the list with its message.
  `loopsOf` replays `remove` and `rename` over the journal as `show` gives it (`withEdits`, a display-only mirror of `apply_edits`).
- **Held Loops:** a held Loop's `region.png` is read into the region Mask as soon as it is built; its reason and `loop.held` show
  inline. The preview plays the other Loops. Accept was already disabled by any error finding.
- **Import frames:** a drop on the frame strip, or a file picker, sends one multipart `import --loop` (`callWithFiles` in `api.ts`: the
  first PNG as `file`, the others as `frames` parts, `kit.json` as `kit`). The kit-folder route stays.
- Tests: `web/e2e/loops-follow-ups.spec.ts` (4); `loops` and `loopedits` specs still pass. Screenshots:
  `web/shots/loops-held.png`, `loops-held-rename.png`, `loops-held-drop.png`.
- Gap for a backend ticket: `show` gives the Loops Decisions as recorded; the screen replays `remove` and `rename` itself. A
  `decisions` view as the Stage reads them would remove that client logic. The `export.id_frozen` inline display has no Playwright test.
