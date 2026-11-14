---
status: todo
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

- [ ] Playwright against `kiripix serve`: flood a region on a new Loop before picking any colour. The region shows, and a
      second, complete Loop plays in the preview.
- [ ] Playwright: rename a Loop, then remove another; `loops.json` matches; `undo` restores the removed one.
- [ ] Playwright: drop two fixture frames and `kit.json` on the strip; both show as thumbnails.

Budget: 100–180k tokens.
