---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: UI: `blink`, `still`, `speed` and transitions on the clips screen

Spec §6.3 (clips), §11. From [0203](../m4/0203-m4-stamped-eyes-blinks-and-still-clips.md)'s "Open" ("The UI has no controls for
`blink`, `still` or `speed`") and [0218](../m4/0218-m4-transition-clips.md)'s out of scope ("a transition's controls are a
follow-up"). Today they're set from the CLI only.

## What to build

On the clips screen ([0157](../m4/0157-m4-ui-edit-a-clip.md)), all through the `clip` and `transition` Decisions:

- **`speed`** and **`still`** fields on a clip, with the resulting frame count shown.
- **`blink`, `wink_left`, `wink_right`:** mark frames on the clip's frame strip (click a frame to toggle it). A blink past the
  last frame is refused by the Decision's own check, and the UI shows that finding.
- **Transitions:** a "new transition" form (`from` clip and frame, `to` clip and frame, `length`). Transitions are listed with
  the clips, and removing a clip shows the transitions that go with it, as `show` lists them.
- A clip from a base (`from_base`) shows its fields read-only, with "change on this character" making the character's own
  Decision, as the screen does for ranges.

## Acceptance criteria

- [x] Playwright, on the fake-Blender fixture: setting `speed` 2 halves the shown frame count and records one Decision;
      marking two frames as `blink` records them; a transition created in the form appears in `show`.
- [x] `npm run build` passes.

## Result (2026-11-17)

Built in `web/src/characterScreens.tsx` (and `styles.css`), all through the `clip`, `transition` and `remove` Decisions, one `decide` per click:

- The clip form has **Speed** and **Still** fields; the shown frame count follows both (`sampleCount` takes `speed`, as `sample_frames` does; `still` shows its own count).
- A **frame strip** under the count: pick Blink, Wink left or Wink right, then click a frame to toggle it. Marks past the last frame are listed in the form, and the `clips.blink_range` finding shows after the run. A clip's row shows its speed, still and marks.
- **Transitions** are listed in their own table, with a "New transition" form (from clip and frame, to clip and frame, length, optional frame rate); a transition is changed under its name. Every clip row has **Remove**, which notes the transitions that go with it, read from the Decisions as `show` lists them. A base's clip or transition says "Change on this character" and "Remove here".
- Playwright (`web/e2e/character.spec.ts`, two new flows): speed 2 takes 12 frames to 6 and records one Decision (blink `[1, 4]`, wink_left `[2]`), a built count of 6, still, and the blink-range finding; a transition made in the form is in `show`, is changed, and removing a clip lists and then drops its transitions. `character-base.spec.ts` and the other clips tests still pass. `npm run build` passes.
- Screenshots: `web/shots/clip-controls-form.png`, `web/shots/clip-controls-transitions.png`.
- A frame past the last one can't be marked in the strip (it has only the clip's frames), so the finding appears only for a Decision made elsewhere or a clip shortened afterwards.

## After review (2026-11-17)

The `clip` Decision now refuses a blink or wink past the last frame of a `still` clip when decided (`decision.invalid`), and the
UI shows that finding at once. A clip without `still` can't be checked then: its frame count depends on the source's frame rate,
which only the Stage reads (by Blender), so its run still fails `clips.blink_range`. The form's live frame count stays a preview
computed in the browser, for the same reason. Tests: `test_character_eyes.py` (both cases), and the Playwright flow updated.
