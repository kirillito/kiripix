---
status: done
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

- [x] CLI seam: two crops, an edit of each, each placed at its own crop's place.
- [x] `--of crop` still takes the latest. Spec §6.1 and the `extend` help say so.

## Result

- `extend <room> crop` writes `extend/crops/<hash>.png` and `<hash>.json` (the name is the first 16 hex of the PNG's hash, like
  a piece) and returns `crops`, every crop's name, oldest first. The same crop again is the same file and becomes the latest.
- `import --of <name>` takes a crop by the start of its hash, like a piece or a Variant (`import.of_ambiguous` if the start
  names several). `--of crop` is the latest (record field `number`). A crop of a Source no longer picked, or whose PNG isn't the
  recorded one, is `import.crop_stale`, by name or as the latest.
- Format change: `crop.json` is `schema_version` 2 (adds `number`). The pure migration `migrate_crop_record` (1 -> 2) is in
  `kiripix/core/settings.py` (`CROP_MIGRATIONS`), beside the Project's and the Asset's. An existing
  Project's `extend/crop.png` and `crop.json` are read in place as the oldest crop, and moved into `crops/` by the next
  `extend crop` (the writing Command).
- Spec §6.1, the `extend` help and the `--of` help say so. Tests: `tests/cli/test_look_edit_of.py` (two crops with an edit
  each, `--of crop` latest, stale by name, an old single crop).
