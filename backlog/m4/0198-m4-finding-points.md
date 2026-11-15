---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: a finding's extra points, and `area.ambiguous_cells` lists all its cells in them

Spec §10 (Findings and errors). Found in the review of [0139](0139-m4-ui-draw-an-area.md).

`area.ambiguous_cells` (0137) asks for the cells "with their positions", but a `Finding` (`kiripix/checks/finding.py`) has
one `position` and forbids other fields, so the cells are only in the message text, and only the first 8 of them ("and N
more"). The place screen reads them out of the message (`ambiguousCells()` in `web/src/markerTool.ts`), so it ties itself to
an f-string and misses every cell past the eighth. The message text is not part of the contract; `code`, `position`, `fix`
and `owner_action` are.

## What to build

- An optional field on `Finding` for the further pixels a finding is about. Recommended: `points`, a list of `[x, y]` in
  target px, absent when unused, so every existing finding and envelope is unchanged. Decide the name and shape with the
  Owner before building: it changes the envelope every Command returns.
- `area.ambiguous_cells` fills it with the top-left pixel of every ambiguous cell, not just 8. The message keeps its short
  list for a human reader.
- The spec's finding shape (§10), and `describe`'s envelope schema if it shows one.

## Acceptance criteria

- [x] CLI seam: a test room with more than 8 ambiguous cells returns all of them in the new field, in a stable order.
- [x] Every other finding's JSON is unchanged (the contract test passes without new samples).

Budget: 40–80k tokens.

## Result (2026-11-14)

- `Finding` gains `points`, a list of `[x, y]` in target px (Owner's decision, 2026-11-14). It is omitted from the JSON when
  empty (a wrap serializer on `Finding`), so every existing finding's JSON is byte-identical and the contract test needs no
  new sample. Input accepts `points` too; no other field changed.
- `area.ambiguous_cells` fills `points` with the top-left pixel of every ambiguous cell, in row order (y, then x). The message
  keeps its short list ("and N more").
- Spec §10 (Findings and errors) names the field. `describe` shows no finding schema, so nothing changed there.
- Tests: `tests/cli/test_area.py::test_every_ambiguous_cell_is_in_points_not_only_the_eight_the_message_lists` (11 cells, and no
  other finding carries `points`).
- Left for the Owner: 0199 should read `points` instead of parsing the message.
