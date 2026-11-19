---
status: todo
milestone: M5
agent: character-pipeline
type: ticket
depends_on: [0303-m5-cell-per-clip.md]
---

# M5: a Wearable follows its body's cell per clip

Left by [0303](0303-m5-cell-per-clip.md): a body clip that doesn't fit the body's cell now has its own larger cell and pivot,
but a Wearable's `render` still draws every clip at the body's top-level cell, so over such a clip the Wearable's frames don't
line up with the body's. `wearable.body_not_exported` compares the top-level cell only.

## What to build

- A Wearable's `render` reads each clip's `frame` and `pivot` from its body's `render.json` and draws that clip at them; its
  `sheet` lays the clip out at the same cell, as the body's does.
- `wearable.body_not_exported` (or a new finding) compares every clip's cell and pivot with the body's.
- Stage `version` bumps.

## Acceptance criteria

- [ ] CLI seam: a body with one wider clip and a Wearable over it: the Wearable's frames of that clip are the clip's cell size,
      and its pivot matches the body's, frame by frame.
- [ ] A body whose clip cell changed makes the Wearable's check fail with the clip named.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
