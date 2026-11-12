---
status: todo
milestone: M4
agent: character-pipeline
type: ticket
parent: 0166-m4-ramps-match-across-characters.md
depends_on: [0150-m4-palette-ramps-per-part.md, 0167-m4-project-ramp-table.md]
---

# M4: the character `palette` Stage reads the Project's ramp table

Spec §6.3 (palette). Part of [0166](0166-m4-ramps-match-across-characters.md).

## What to build

- **`parts` names parts of the table** when the table isn't empty. A part is `name` (its material has the same name) or
  `name=materials` (`top=jacket+hood`), so two Models with differently named materials map to the same part. A part not in the
  table fails the Stage with `palette.part_not_in_table`, listing the table's parts; its `owner_action` is to add it with
  `ramps-add`. A per-character length (`skin:4`) is refused when the table has the part. With an empty table, `parts` works as
  0150 built it.
- **The table is an input of `palette`:** a change to it makes every character's `palette` stale; `render` stays done.
- **Lengths come from the table.** A part without `rgb` is fitted as in 0150, at the table's length.
- **A part with `rgb` isn't fitted:** its pixels are mapped onto the given ramp by lightness order (OKLab L), so a darker or
  lighter texture than the first character's still uses every step, dark to dark. Golden-test the mapping Op (in `ops`, with
  0149's).
- **Every `rgb` colour of the table is reserved** in a character that has any table part, even a part it lacks: no fixed
  colour, other part or the outline uses it, so a hair swap can't recolour a hairless character's jacket.
- `palette.json`'s `parts` gains each part's `row` (its index in the table) and `shared` (true when the colours came from the
  table). Bump its `schema_version`.

## Acceptance criteria

- [ ] CLI seam, on the fake: two characters with materials named differently, mapped to the same table parts, get the same rows
      and lengths in `palette.json`, and the same colours for a part with `rgb`.
- [ ] Changing the table makes both characters' `palette` stale and neither's `render`.
- [ ] `palette.part_not_in_table` is raised with an `owner_action`; `palette.ramp_shared` still holds, now across the reserved
      colours too.
- [ ] A golden test: a part with a lighter and a darker texture both use every step of a 3-colour given ramp.
- [ ] On mc02 with a table filled from mc02 itself: the 52 px frames are byte-equal to 0150's (same ramps, same order).

Budget: 150–250k tokens.
