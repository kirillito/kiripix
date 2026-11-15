---
status: todo
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

- [ ] Playwright, on the fake Blender: a character made from a base shows its base, the base's clips as the base's, and a
      parameter from the base with its mark; removing a base clip records a `remove` Decision.
- [ ] A generated character's Model screen shows its parameter file and offers no Pick.
