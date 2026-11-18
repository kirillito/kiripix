---
status: todo
milestone: M5
agent: character-pipeline
type: ticket
parent: 0236-m5-the-games-next-needs.md
depends_on: [0300-m5-clip-attach.md]
---

# M5: import a held thing: its mesh and its materials

Part of the held-things build chosen in [0238](0238-m5-held-things-trial.md) (the Owner, 2026-11-18): option (a), the thing
attached in the character's render for the clips that hold it, at a `grip_r` socket bone, with a cell per clip and a ramp row for a
class weapon. The trial's prototype (`backlog/m5/0238-trial/`, `held_render.py`, `grip_config.json`) is the reference.

## What to build

- **`import --role thing --thing <id>`:** a mesh file (`.glb`, or a `.blend` object) stored per Asset under `src/things/<id>/`, its
  materials listed. A thing's origin and axes are its grip: the trial set them per thing in `grip_config.json`; the import keeps the file's
  own, and the clip's `offset` and `turn` adjust them.
- The thing's materials are numbered after the Model's (the Model's 1 to N stay put; 0170, 0238: the phone, screen and stick were 13 to 15),
  in a stable order per thing, so a material pass keeps its meaning when a thing is added.
- `show` lists the Asset's things and their materials.

## Acceptance criteria

- [ ] CLI seam: a thing is imported, listed with its materials, and re-imported under its ID as a new Variant; a thing a clip
      attaches can't be removed while attached.
- [ ] `uv run lint-imports` and `uv run mypy` pass.
