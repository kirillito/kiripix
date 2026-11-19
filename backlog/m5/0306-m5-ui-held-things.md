---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0302-m5-render-attached-things.md]
---

# M5: UI: a clip's held things, and their socket on the frames

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- On the clips screen, a clip's `attach` (thing, socket, offset, turn) edited as a Decision; the Asset's things listed with their imports.
- On the frames, the socket's point drawn (with [0284](0284-m5-ui-show-points-on-the-frames.md)'s points), so the Owner checks that each thing
  sits in the hand.

## Acceptance criteria

- [x] Playwright: on a built fixture with a thing, attaching it to a clip records the Decision, and the socket's point shows on the frames.
- [x] `npm run build` passes.

## Result

- **Clips screen** (`web/src/characterScreens.tsx`): a "Holds" column in the clip table; a "Holds" section in the clip form, a row per held
  thing (thing from `show.things`, socket with the rig's bones as suggestions and `grip_r` as the default, offset and turn as x/y/z numbers),
  saved with the clip as one `decide` carrying `attach` (nothing sent when the clip holds nothing, so letting go is a `decide` without it).
  A "Held things" list: each thing's Variants, materials (number and index), the clips that hold it, and Remove (`thing-remove`, disabled while a
  clip holds it); a name field and a drop zone for `import --role thing --thing <id>`. The Commands' refusals (`clips.unknown_thing`,
  `clips.unknown_socket`) show through the usual findings.
- **The socket's point** needed no new code: `render` records it as a point named after the bone (`rightforearm`), and 0284's frame screen draws it.
- `web/src/api.ts` (`HeldThing`, `ShowData.things`), `web/src/App.tsx` (`import` passes `thing`; `thing-remove`).
- Test: `web/e2e/held-things.spec.ts` (fake Blender, `render_thing.glb`): import a thing, attach it to a clip (one Decision, checked through `show`),
  render, the `rightforearm` point on the frame at the recorded pixel, let go, import and remove a second thing. Screenshots:
  `web/shots/0306-held-thing-point.png`, `web/shots/0306-held-things.png`.
- **Backend bug found (fixed in the main session, 2026-11-18: `attached_by` reads `graph.decisions`; test `test_a_thing_a_clip_lets_go_of_can_be_removed` in `tests/cli/test_held_things.py`):** `kiripix/core/things.py` `attached_by` reads `graph.replay("clips").current`, which still holds a
  clip's earlier Decisions of the same name. After a clip is decided again without `attach`, `show` still says the thing is held by it, and
  `thing-remove` refuses with `thing.attached`. It should read the Decisions as the Stage reads them (`graph.decisions(spec)`, after `decisions_view`).
  The e2e removes a thing no clip ever held until this is fixed.
