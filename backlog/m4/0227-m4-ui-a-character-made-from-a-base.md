---
status: done
milestone: M4
agent: ui-engineer
type: ticket
---

# M4: UI: a character made from a base, and a generated one

Spec §6.3 and §11. From [0165](0165-m4-characters-share-a-base.md) and
[0224](0224-m4-a-model-built-from-a-parameter-file.md) (ADR 0012), built 2026-11-14 on the Command side only.

## The gap

`show` now says what the character screens don't show yet:

- `base`: the character this one is made from.
- `stages[].param_sources`: where each parameter's value comes from (`asset`, `generated`, `base`, `default`).
- `stages[].decisions[].from_base`: a Decision that is the base's. `undo` on the character never takes it back.
- `clip_sources`: the base's files too, with a `file` in the base's folder.
- `parameters`: a generated character's parameter file, in place of Variants.

So today a clip from the base looks like the character's own (and can't be undone), a value from the base or the generator
looks typed, and a generated character's Model screen shows no Source.

## What to build

- **Model:** the base, as a link to it; for a generated character, the parameter file (name, and import by drag-and-drop
  with `import --role parameters`) in place of the Variant list. No Pick is offered.
- **Rig:** for a character made from a base, no Mixamo steps; `rig.base_mismatch` shown with its bones.
- **Clips:** the base's clips marked as the base's, read-only, each with "change here" (a `clip` Decision of the same name)
  and "remove here" (a `remove` Decision); the base's clip sources marked the same way.
- **Every Stage's parameters:** a small mark on a value that comes from the base or the generator, and "set here" to
  override it.
- **`new`:** the `base` choice for a character.

## Acceptance criteria

- [x] Playwright, on the fake Blender: a character made from a base shows its base, the base's clips as the base's, and a
      parameter from the base with its mark; removing a base clip records a `remove` Decision.
- [x] A generated character's Model screen shows its parameter file and offers no Pick.

## Result (2026-11-15)

Built in `web/` on the existing Commands only (`show`, `new`, `import --role parameters`, `decide`, `set`, `undo`); no Command was missing.

- **Model:** a link to the base; for a generated character, its parameter file (name, size, drop to replace with `import --role parameters`) in place of
  the Variant list and its drop, so no Pick. A character with no Model yet also gets a parameter-file drop.
- **Rig:** for a character with a base, no Mixamo steps, upload or rigged-file drop; a note on the skeleton rule; a failed `rig` shows its reason, which
  names the base and the missing or re-parented bones.
- **Clips:** the base's clips marked "the base's", with "Change here" (the existing form, a `clip` Decision of the same name) and "Remove here" (a `remove`
  Decision). A `remove` hides the clip; a changed one becomes the character's own. The base's clip sources are marked the same way (their `file` is in the base's folder).
- **Parameters:** every Stage panel marks a value from the base ("from the base") or the generator ("generated"), with "set here", one `set` of the shown value.
- **New:** the Status board has a "New character" form (name, base, optional parameter file; one `new`), which opens the new character.
- **Tests:** `web/e2e/character-base.spec.ts` (4 flows, fake Blender, the fake generator for the generated one). `character.spec.ts` and `shell.spec.ts` still pass.
  Screenshots in `web/test-results/`.
