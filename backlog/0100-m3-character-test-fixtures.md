---
status: todo
milestone: M3
agent: qa-engineer
type: ticket
parent: 0097-m3-characters.md
---

# M3: character test fixtures and the `blender` marker

Spec §12 (tests: "Blender tests marked and skipped when Blender is missing") and the testing decisions of
[0097](0097-m3-characters.md).

The character tickets need small Models to test on, with a licence that lets them sit in this repo. A Mixamo download
can't be used: its terms don't cover redistribution in a public test suite.

## What to build

- A committed bpy script under `tests/fixtures/` that builds, in Blender 5.2, a tiny rigged humanoid (a few hundred
  triangles, Mixamo-style bone names, two coloured parts so a palette has something to map), with two short actions: one
  stationary (an idle) and one with the feet moving in place (a walk). It writes a `.glb` and an `.fbx`.
- A second fixture with no armature, for the `rig` Stage's "no rig" path.
- The outputs committed in LFS, with `.gitattributes` lines for `tests/fixtures/**/*.glb` and `*.fbx`.
- A `blender` pytest marker in `tests/conftest.py` and `pyproject.toml`: the test is skipped when no Blender is found on
  `PATH` or in `KIRIPIX_BLENDER`, or when its version isn't 5.2.x, with the reason in the skip.

## Acceptance criteria

- [ ] Running the script reproduces the fixtures; the command is in its docstring.
- [ ] A marked test that only opens each fixture in Blender passes with Blender and is skipped without it, with a clear reason.
- [ ] `uv run pytest` on a machine without Blender reports the skips and nothing else changes.
