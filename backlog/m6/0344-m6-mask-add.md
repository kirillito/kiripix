---
status: done
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

- [x] CLI seam: `masks-add cover` then a brush Decision on `cover` builds `masks/cover.png` in the `masks` Stage's output;
      `reach` is unchanged.
- [x] CLI seam: a taken colour and a reserved name are refused.
- [x] `masks-add` has a sample in `tests/cli/test_contract.py`.
- [x] Spec §4, §6.1, §10.5 and §14's Later list updated (named Masks move to M6).

## Result

- `kiripix masks-add <name> --colour #RRGGBB --meaning "<text>" [--view top|side]` (`kiripix/commands/masks.py`): a `writing`
  Command an agent may run (MCP exposed; the ticket says an agent edited the file by hand, so it isn't owner-only), under the
  Project lock, atomic and comment-keeping (`save_settings`). Refusals: `masks.name_invalid`, `masks.name_taken` (also
  `walkable`, `foreground`, `import`), `masks.colour_invalid`, `masks.colour_taken` (another Mask's colour or an import
  colour of the view; compared case-insensitively, stored upper-case).
- `describe room` carries `masks` (a `MaskRow` each: `view`, `name`, `colour`, `meaning`, `derived`, `blocks`; top view first,
  then side, each in file order) and `masks_example`. `MaskRow` and `mask_rows` are in `kiripix/commands/mask_table.py` for
  0345 and 0346 to reuse. `blocks` is true only for `solid` and `pit`.
- `masks` Stage: a Decision on a Mask no longer in the Project now fails with code `masks.unknown` (was `stage.failed`), a
  `fix` (`kiripix undo <room> masks`) and a message that names the Mask, the Decision and `masks-add`; exit 1 as before.
- `MaskDefinition` no longer dumps `derived = false`, so a written painted Mask reads like the Owner's. No schema bump, no
  Stage `version` bump (the hash is unchanged).
- A new Mask is written as a `[masks.<view>.cover]` table at the end of the view's tables; it is valid TOML, but not an
  inline table in line with `solid`. Left for the Owner: say if inline tables are wanted.
- Spec (§4 example, §6.1, §10.5 list, glossary table) and GLOSSARY.md updated; §14's Later list already said named Masks moved
  to M6.
- Tests: `tests/cli/test_masks_add.py`; samples in `test_contract.py` and `test_serve.py`; `index.py` regenerated.


**Review fixes (2026-11-20):** `masks.unknown` carries an `owner_action` (undo the Decision or add the Mask back: the Owner removed the Mask, so whether its painting goes too is theirs), so `run` exits 3. `masks.name_invalid` and `masks.colour_invalid` carry a `fix` with the corrected command (an input slip, not a choice); `masks.name_taken` and `masks.colour_taken` stay the Owner's. `reach` unchanged is now tested: `test_a_named_mask_across_the_floor_leaves_reach_unchanged` in `test_reachability.py`. The painted-Masks lookups share `MaskSet.definitions()` and `painted()` (core) and `_view_masks` (the room recipe).
