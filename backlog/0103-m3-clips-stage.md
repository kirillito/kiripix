---
status: todo
milestone: M3
agent: character-pipeline
type: ticket
parent: 0097-m3-characters.md
depends_on: [0102-m3-rig-stage-and-mixamo.md]
---

# M3: the `clips` Stage

Spec §6.3 (clips). Story 6 of [0097](0097-m3-characters.md). Q5 (names) is answered in 0097: clip IDs are snake_case verbs,
and refused if they end in a direction suffix (`_s`, `_sw`…). Q10 (stationary clips): ask the Owner before fixing the
Decision's schema.

The `clip` Decision is declared today with `name`, `source`, `start`, `end`, `fps` and `loop`.

## What to build

- The Stage resolves each current `clip` Decision against its source: an action in the rigged Model, or an animation file
  added through [0099](0099-m3-core-for-characters.md). It writes `clips.json` (`schema_version`, each clip with its source's
  hash, frame range, frame rate, loop flag, and the frame numbers a render will sample at `fps`).
- A clip name is an ID that will be frozen at export: lower-case, `[a-z0-9_]`, unique in the character.
- Root motion: a clip whose root travels is reported (`clips.root_motion`), with an `owner_action` to download it "in place"
  from Mixamo. The render keeps the feet at the pivot.
- If the Owner decides stationary clips are flagged (Q10), add the flag to the Decision's schema here.
- No clips: `needs-input`, with the Decision's shape in the finding.
- Checks: `clips.source_missing`, `clips.range` (outside the action's frames), `clips.duplicate_name`.

## Acceptance criteria

- [ ] CLI seam, on the fake: three `clip` Decisions build `clips.json` with the sampled frame numbers; `undo` removes one.
- [ ] A missing source, an end past the action and a duplicate name each give their finding.
- [ ] `describe character --stage clips` shows the final schema, and its contract sample passes.
