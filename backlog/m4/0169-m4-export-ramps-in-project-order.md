---
status: todo
milestone: M4
agent: godot-export
type: ticket
parent: 0166-m4-ramps-match-across-characters.md
depends_on: [0151-m4-export-part-ramps.md, 0168-m4-palette-reads-the-ramp-table.md]
---

# M4: `ramps.png` rows in the Project's order, the same on every character

Spec §9 (Character). Part of [0166](0166-m4-ramps-match-across-characters.md).

## What to build

- With a non-empty ramp table, `ramps.png` has one row per part **of the table**, in its order, not per part of the character.
  A part the character doesn't have is a fully transparent row. Rows are padded to the table's longest ramp.
- `metadata/kiripix_parts` lists the table's part names in row order, so it's the same on every character of the Project.
- `character.json`'s `parts` carries each part's `row` and `shared` from `palette.json`, in row order. Bump its
  `schema_version` (refused when old, per CLAUDE.md: re-export, no migration).
- With an empty table, export as 0151 built it.

## Acceptance criteria

- [ ] CLI seam: two fake characters, one without `hair`, export `ramps.png` of the same height with `hair` on the same row, the
      second's transparent; `metadata/kiripix_parts` is identical in both scenes.
- [ ] A re-export writes nothing.
- [ ] In Godot 4.7 (headless, as 0151): one test shader, given the same replacement for the skin row, recolours only skin on
      every character of the Project that has the four Assets built (or mc02 and one other, until they are).

Budget: 60–120k tokens.
