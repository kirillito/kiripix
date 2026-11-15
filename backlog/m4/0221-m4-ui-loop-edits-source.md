---
status: done
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

- [x] Playwright: an edits Loop with two imported frames; picking one shows it in the strip; drawing a `hold` over the
      top half and building shows the top half equal in both frames.
- [x] `npm run build` passes.

Budget: 80–150k tokens.

## Result (2026-11-14)

- **Source choice.** `source-edits` joins Op and Kit on a frames Loop (a `frames` Decision with `source: "edits"`); the "waits for
  trial 0184" hint is gone. A Loop with picks and no `frames` Decision shows as Edits.
- **Per frame.** A Frame field (default: one past the last picked frame), an import button and a hidden file input. One import is
  `import <id> --loop --frame` (REST `file`) and one `pick` of the Variant it returned, as an edit of a Look is imported and picked at
  once; the panel says "Edit the room's Source each time, not an earlier edit." `import.edit_of_an_edit` shows beside that frame's
  line, and on its thumbnail badge. Importing to the same frame again picks the new one.
- **Hold.** "Hold from this frame" on each thumbnail of frame 1 on turns the polygon, brush and erase tools into `hold` Decisions of
  that frame (one `decide` on release; flood, eyedropper and anchor end the hold mode). The held part is shaded as a second Mask
  tint; the loop list says "N px held" from `loops.json`. The preview plays the built frames, so the still part stops once built.
- **Badges.** `loop.misaligned` and `loop.drift` by `field` `loop.<id>.frame.<n>`; `loop.flicker` on both frames of its pair
  (the finding's frame and `from` read from `loops.json`'s `flicker`, one badge a frame when two pairs meet); `loop.past_layer` on
  every frame from 1 on.
- **Gaps for the backend.** `show` lists no Variants of a Loop's frames (only a Look's), so the screen can't offer picking an earlier
  edit of a frame; it imports again instead. (Since the review of 2026-11-14 the Stage writes the held pixels as
  `<loop>/hold.png`, named by `holds.file` in `loops.json`, and the screen shades that file; `heldSet` is gone.)
- Tests: `web/e2e/loopedits.spec.ts` (2), run with `loops.spec.ts` at one worker (6 tests there, all pass); at the default workers
  `loops.spec.ts` times out (ticket 0202).
