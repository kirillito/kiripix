---
status: done
milestone: M4
agent: ui-engineer
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0156-m4-edit-a-clip.md]
---

# M4: edit a clip on the clips screen

Spec §11 (the UI) and §6.3 (clips). The UI half of [0156](0156-m4-edit-a-clip.md), found at the M3 gate.

## What to build

- On the clips screen's table, each row gets **Edit**, which fills the "Add a clip" form with that clip (its name locked)
  and turns the button into **Change clip**. It sends the `clip` Decision again under the same name (0156).
- The form shows how many frames the range gives at its fps, by the rule `clips` uses (`sample_frames` in
  `kiripix/recipes/clips.py`, with the source's frame rate the screen already shows), so the Owner can aim for "10 to 20
  frames" without a render.
- Cancel puts the form back to adding.

## Acceptance criteria

- [x] Playwright, on the fake renderer: edit idle's end, change it, and the table shows the new range; walk and attack are
      unchanged.
- [x] The form's frame count matches `clips.json`'s frame count for that clip after the run.

## Done

The frame count needs the source's frame rate. A clip-source file's and the rigged file's came from the `inspect` Probe, but a
clip from the Model's own actions had none. Fixed 2026-11-12: `normalise_model.py` returns the file's `fps` (read as
`read_actions.py` reads it), `model.json` carries it as an additive key (`schema_version` stays 2), and the clips screen counts
the Model's own actions' frames from it. A `model.json` built before has no `fps` and shows no count until `model` runs again.
