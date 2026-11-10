---
status: done
milestone: M3
agent: core-engineer
type: ticket
parent: 0097-m3-characters.md
depends_on: [0101-m3-blender-launcher-and-model-stage.md]
---

# M3: `show` gives a character's files their original names and sizes

Spec §5 (Sources) and §11. Found in [0114](0114-m3-ui-model-rig-clips-screens.md). A Model Variant is stored as
`src/<hash>.<ext>` by design (`kiripix/core/sources.py`), so the Model screen lists hashes: the Owner can't tell
`hero_v2.fbx` from `hero_old.glb`. The screen gets each file's size by a Range request to the file route, which is a transport
detail standing in for something `show` should say.

## What to build

- `import` records the file name each Variant, rigged file and clip source was imported with, in a data file that carries
  `schema_version`, writes atomically, and is append-only if it is a `.jsonl` (`src/imported.jsonl` is the obvious place;
  check the spec for a better one). It records only. The stored file names and the hash naming don't change.
  Importing the same content twice under a new name records the newer name.
- `show` gains, for each Variant, the rigged file and each clip source: `imported_as` (the original file name, or null for
  files imported before this ticket) and `size` (bytes).
- If this applies equally to image Variants (rooms, props), do it for them too. The same rule gives the same field.

## Acceptance criteria

- [ ] CLI seam: import `hero_v2.fbx`, and `show --json` gives `imported_as: "hero_v2.fbx"` and its size. A Project from
      before this ticket gives `imported_as: null` and no error.
- [ ] The contract sample for `show` is updated.

Budget: 40–80k tokens.
