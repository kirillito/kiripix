---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0152-m5-character-layers.md
depends_on: [0291-m5-wearable-model-rig-render.md]
---

# M5: a Check: where stacking by order differs from stacking by depth

Part of [0152](0152-m5-character-layers.md). From the trial [0153](0153-m5-character-layer-trial.md)'s Results and the Owner's answers (2026-11-18).

## What to build

- `wearable.stack_differs` (info), on the body once its Wearables are built: stack them by `order` and by depth, and report per clip
  and direction the pixels that differ, with the worst frames' boxes (the trial's measure, `0153-trial/compare.py`). It shows
  the Owner where a game stacking by order alone is wrong (in the trial: a pack's edges, a leg in front of a coat's hem).
- The stacking is pure Ops in `kiripix.ops`; the Check reads the built sheets.

## Acceptance criteria

- [x] Golden seam: stacking by order and by depth on small fixture frames, pixel-exact.
- [x] CLI seam: the finding, with counts and boxes, on a fixture body with two Wearables.

## Result

- **Ops** (`kiripix/ops/stack.py`): `stack_by_order` (lowest first, each pasted over the last where it has alpha), `stack_by_depth`
  (nearest of the 16 bit depth passes wins; a tie goes to the later frame, as the trial's `zmerge`) and `stack_difference` (alpha
  or colour differs, the trial's `differ`). Goldens: `tests/golden/test_stack.py`, `expected/stack_by_order.png`,
  `stack_by_depth.png`, `stack_difference.png`.
- **Check** `wearable.stack_differs` (info; `kiripix/checks/stack.py`, computed by `recipes/wearable_stack.py`): on the body's
  `render` (the character's `render` Stage now has `check` and the `CheckSpec`). One finding per clip with a difference: the
  differing px over the clip against the px shown, per direction, and the three worst frames with their boxes (x, y, w, h); its
  position is the worst frame's box, `fix` is `kiripix show <body> render`. It reads each built Wearable's `render` colour and
  depth frames and the body's, not sheets (0293 comes after); it is silent until one Wearable's `render` is built, and skips a
  frame whose size differs (a stale Wearable).
- **Core hook** (small): `StageSpec.worn_stage` and `StageRun.wearing` (Wearable ID to its built output folder of that Stage,
  ID order), filled by `graph._wearing`. Only the character's `render` sets it.
- **Order:** `order` doesn't exist yet, so the stack uses the default: the Wearables in ID order above the body. I did not add `order`
  to the Wearable's `render`: it doesn't change the render, and setting it would make the render stale. 0293 adds it (on `sheet`);
  the Check then reads it instead of the ID order.
- **No version bump:** no Stage's output changed.

