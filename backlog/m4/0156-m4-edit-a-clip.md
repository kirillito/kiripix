---
status: done
milestone: M4
agent: character-pipeline
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
---

# M4: change a decided clip's frames, keeping its name

Spec §6.3 (clips). Found at the M3 gate ([0117](../m3/0117-m3-gate.md)), 2026-11-11.

## The gap

Mixamo's idle on mc02 is source frames 1 to 251, which at 12 fps is 100 frames in every direction. The game wants 10 to 20,
played on a timer once the player stops. A `clip` Decision already has `start` and `end`, so a shorter idle is just another
range. But a decided clip can't be changed:

- a second `clip` Decision with the same name fails `clips.duplicate_name`;
- `undo` takes back only the latest Decision, so changing the first clip (idle) means undoing walk and attack too and deciding
  all three again.

The clip's name is its frozen ID once exported ([0113](../m3/0113-m3-character-export.md)), so the change must keep it.

## What to build

- A `clip` Decision whose `name` is already a current clip **replaces** that clip, keeping its place in the list. The
  journal keeps both, so `undo` of the new one brings the old range back. A replacement is not a rename, so the exported
  IDs stay as they are.
- `clips.duplicate_name` stays only for a clip whose name appears twice where neither replaces the other, if that can still
  happen. Otherwise drop the code and say so in `describe`.
- `render` reuses every other clip's frames (0119); only the changed clip renders again.
- The Decision's `description` says that deciding a clip again under its name changes it.

## Acceptance criteria

- [x] CLI seam: deciding `idle` again with a shorter range changes `clips.json`'s idle to the new frames, keeps walk and attack
      as they were, and `render` renders only idle.
- [x] `undo` of that Decision restores the old range.
- [x] After an export, changing idle's range and exporting again succeeds with the same `idle_<dir>` IDs and fewer frames.
