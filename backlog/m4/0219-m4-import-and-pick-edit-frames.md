---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0193-m4-loop-kit-and-import.md, 0129-m4-look-variants.md]
---

# M4: import and pick a Loop's edit frames

Part of [0183](0183-m4-ambient-animation.md), route (c): 0193's Part B, kept by trial
[0184](0184-m4-ambient-animation-trial.md). Spec §10 (Commands) and §6.1 (Looks: `import --look`, `pick --look`).

The Owner made a TV's news broadcast from six image-model edits of the kitchen's Source, in about 15 minutes. It was the
Loop that made the room feel most alive. The edits were made one from another, and each was worse than the last (median ΔE
outside the screen 1.65, 2.61, 3.65, 4.67). So an edit frame must be an edit of the Source.

## What to build

- `kiripix import <id> <png> --loop <loop> --frame <n>` (n from 1; frame 0 is the room and is never imported): adds a
  Variant of that frame, as `import --look` adds one of a Look.
- `kiripix pick <id> <variant> --loop <loop> --frame <n>`: chooses it, recording the hash of the room's Source. A new Source
  puts every edit frame in `needs-input` ("made on another Source").
- **Made from the Source.** On `import --loop --frame`, compare the edit with the Source outside the Loop's region, after
  resizing it to the Source's size (`resize_nearest`). If its median ΔE there is more than twice the first imported frame's
  and over 2.5, an info finding `import.edit_of_an_edit` says so, with the owner_action "make each edit from the Source,
  not from another edit". In the trial, the first edit measured 1.65 and the chained ones 2.61 to 4.67.
- A frame Loop's `frames` Decision takes `source: "edits"`. A frame Loop's frames come from one source only: a kit and edit
  frames on the same Loop are refused.
- `describe`, the Commands' schemas and contract samples; `next` names `import --loop --frame` for an edits Loop with a
  frame missing.

## Acceptance criteria

- [ ] CLI seam: two edit frames imported and picked; a new Source puts them in `needs-input`.
- [ ] CLI seam: importing frame 0 is refused; a frame made from another edit (a test image with its outside changed by
      more) raises `import.edit_of_an_edit`.
- [ ] Contract samples for the new flags pass.

Budget: 80–130k tokens.
