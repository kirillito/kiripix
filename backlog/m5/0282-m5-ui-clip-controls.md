---
status: todo
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

- [ ] Playwright, on the fake-Blender fixture: setting `speed` 2 halves the shown frame count and records one Decision;
      marking two frames as `blink` records them; a transition created in the form appears in `show`.
- [ ] `npm run build` passes.
