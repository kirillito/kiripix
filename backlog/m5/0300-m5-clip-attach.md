---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: a `clip` Decision's `attach`: the thing a clip holds, at a socket

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **`attach` on a `clip` Decision:** a list of held things, each `thing` (a held thing's ID, 0301), `socket` (a bone of the Model,
  default `grip_r`) and an optional `offset` (x, y, z in the socket's frame, Model units) and `turn` (degrees about each axis). A clip
  without `attach` holds nothing; a `transition` holds what its `from` clip holds.
- Validation: the thing exists on the Asset, the socket is a bone of the rigged Model (`clips.unknown_socket`, with a `fix` naming the
  `rig` bones), no thing twice in one clip. `describe` and `schema` show the field.
- `clips` Stage `version` bump; the clip table (`[[character.clips]]`, 0239) doesn't carry `attach` (a class's weapon differs by body).

## Acceptance criteria

- [ ] CLI seam on the test Kind or a fixture character: a clip with `attach` is recorded and listed by `show`; an unknown thing or
      socket is refused with its finding; a transition inherits its `from` clip's things.
- [ ] Contract samples updated; `uv run lint-imports` and `uv run mypy` pass.
