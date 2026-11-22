---
status: done
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0352-m6-one-way-exit.md]
---

# M6: UI: a one-way Exit on the place screen and in the district view

Spec §6.1 (`place`, Exit pairing) and §11. The UI half of [0352](0352-m6-one-way-exit.md), which built `one_way` on an Exit
Marker and the `one_way` pairing in `district`, and left `web/` alone while other UI tickets ran.

## What to build

- **The place screen's Exit form:** a "One-way" checkbox, writing `one_way` in the `marker` Decision (absent or `false` when
  unchecked, as the CLI does).
- **The district view** ([0330](0330-m6-ui-district-view.md)): an Exit whose pairing is `one_way` is drawn as an arrow with
  one head, from the Exit to its target; `paired` keeps its two heads and `unpaired` its warning.

## Acceptance criteria

- [x] Playwright against a real `kiripix serve`: checking "One-way" on an Exit records one Decision with `one_way: true`, and
      the district view draws that Exit with one head.
- [x] `npm run build` passes.

## Result

- **Place screen** (`web/src/roomScreens.tsx`): the Exit form has a "One-way" checkbox (`marker-one-way`). Checked, the `marker` Decision carries `one_way: true`; unchecked, the key is absent (as the CLI does). Selecting an Exit loads its `one_way` into the checkbox.
- **District view** (`web/src/districtView.tsx`): an Exit row is drawn with one head (`→`) unless `paired`, which has two (`↔`); each row has `data-heads`. `unpaired` keeps its warning and link, `one_way` shows the label "one way". The view lists Exits as text rows, so the arrow is a glyph, not a drawn graphic.
- **Test:** `web/e2e/one-way-exit.spec.ts` (one Decision with `one_way: true`; district shows `data-pairing=one_way`, `data-heads=1`). Screenshot `web/shots/district-one-way.png`. `npm run build` passes; the new spec, `district.spec.ts` and `place.spec.ts` pass (14 tests).
- No backend gap. (Mid-run, `kiripix init` failed for a while with a `KeyError` in `core/project.py`, another agent's edit; it cleared by itself.)
