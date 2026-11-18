---
status: todo
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0302-m5-render-attached-things.md]
---

# M5: a held thing's colours: a ramp row for a class weapon, fixed colours for the rest

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **A class weapon gets a row in the Project's ramp table** (the Owner, 2026-11-18): its materials are a part (`stick`, `rake=rake+rake_head`,
  length 2), so its colours are its own and a skin or hair swap never reaches them. 0238: with a row, the body's fixed colours are
  identical to before (0 pixels differ); in fixed colours the palette re-chose 9 of the 16 fixed colours.
- **Anything else held** (the phone) takes fixed colours outside every part, and the fixed subset is chosen so a thing added later doesn't
  move the body's fixed colours (or a warning names the body pixels that moved).
- The `palette` and `finish` Checks tolerate a material absent from most clips (a thing appears only where attached).
- Stage `version` bumps where outputs change.

## Acceptance criteria

- [ ] CLI seam: a fixture with a thing on a ramp row: the body's pixels in a clip without the thing are byte-identical before and after
      the thing is added; with fixed colours, a moved fixed colour is reported.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
