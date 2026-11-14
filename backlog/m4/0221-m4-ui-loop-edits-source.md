---
status: todo
milestone: M4
agent: ui-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0196-m4-ui-frame-loops.md, 0219-m4-import-and-pick-edit-frames.md, 0220-m4-loops-build-edit-frames.md]
---

# M4: the Edits source on the loops screen

Part of [0183](0183-m4-ambient-animation.md), route (c): 0196's Part B, kept by trial
[0184](0184-m4-ambient-animation-trial.md).

## What to build

- **Source choice:** Edits joins Op and Kit (0196 hid it, with a hint that it waits; remove the hint).
- **Per frame:** import and pick a Variant, as on the looks screen. The import panel says, beside the file input: "Edit the
  room's Source each time, not an earlier edit." `import.edit_of_an_edit` shows on that frame.
- **Hold:** draw a `hold` with the polygon or brush tool, and choose its frame from the strip. The held part is shaded on
  the canvas. The live preview plays the built frames, so the still part stops boiling as soon as the `hold` is built.
- **Badges:** `loop.misaligned`, `loop.drift`, `loop.flicker` and `loop.past_layer` on the frame thumbnails; `loop.flicker`
  on both frames of its pair.

## Acceptance criteria

- [ ] Playwright: an edits Loop with two imported frames; picking one shows it in the strip; drawing a `hold` over the
      top half and building shows the top half equal in both frames.
- [ ] `npm run build` passes.

Budget: 80–150k tokens.
