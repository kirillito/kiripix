---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0232-m5-look-edit-of-a-piece-or-crop.md
---

# M5: several crops of a room, each named, so an edit comes back to its own crop

Found in review of [0232](0232-m5-look-edit-of-a-piece-or-crop.md) (2026-11-17).

## The gap

`extend <room> crop` writes one slot, `extend/crop.png` and `crop.json`. A second crop replaces the first, so an edit of the
first, imported with `--of crop`, registers against the second crop's place. Registration may catch it
(`import.of_misregistered`), but a flat crop falls back to the recorded place (`import.of_unregistered`, info) and is placed
wrongly without an error. The Owner may want two crops of one room at once, for two Looks.

## What to build

- `extend crop` writes `extend/crops/<hash>.png` with its record, named by the PNG's hash like a piece, and lists the crops.
- `import --of <hash>` finds a crop as it finds a piece or a Variant. `--of crop` stays and means the latest crop.
- A crop of a Source that is no longer picked is refused, as now (`import.crop_stale`).

## Acceptance criteria

- [ ] CLI seam: two crops, an edit of each, each placed at its own crop's place.
- [ ] `--of crop` still takes the latest. Spec §6.1 and the `extend` help say so.
