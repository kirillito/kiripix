---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: `kiripix masks-add`: a named terrain Mask for the game's grid

Spec §4 (`[masks]` in `kiripix.toml`), §6.1 (masks) and §14 (Later until 2026-11-19: "custom named Masks"). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md).

## The gap

A Project can already name more painted Masks under `[masks.top]` in `kiripix.toml` (a `colour` and a `meaning`), and the
`masks` Stage paints any of them. Only `solid` and `pit` block anything in Kiripix; any other Mask is "the game's to read"
(`kiripix/recipes/room.py`, `_COLLISION_MASKS`). But no Command adds one, so an agent edits the file by hand, and the
export and the UI don't carry them yet ([0345](0345-m6-export-named-masks.md), [0346](0346-m6-ui-named-masks.md)). The game's
M09 (a grid battle in a large room) reads terrain per cell: `cover`, `water`, `high`.

## What to build

- `kiripix masks-add <name> --colour #RRGGBB --meaning "<text>" [--view top|side]` adds a painted Mask: an atomic write that
  keeps the file's comments, as the other `*-add` Commands do. A name is snake_case, and not `walkable`, `foreground`, or an
  existing Mask. A colour already used by another Mask of the view is refused (`masks.colour_taken`).
- A named Mask is **never** collision or walkability in Kiripix. `reach` and the walk test ignore it. Say so in the spec and
  the glossary ("Mask": named Masks have no meaning in Kiripix, as areas have none).
- `describe room` lists the Project's Masks with their meaning, so a session finds them.
- A Mask that is removed by hand while rooms have Decisions on it: those Decisions are refused at replay with
  `masks.unknown`, naming the Mask and the Decision.

## Acceptance criteria

- [ ] CLI seam: `masks-add cover` then a brush Decision on `cover` builds `masks/cover.png` in the `masks` Stage's output;
      `reach` is unchanged.
- [ ] CLI seam: a taken colour and a reserved name are refused.
- [ ] `masks-add` has a sample in `tests/cli/test_contract.py`.
- [ ] Spec §4, §6.1, §10.5 and §14's Later list updated (named Masks move to M6).
