---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0349-m6-to-paint-pack.md]
---

# M6: `kiripix inbox`: import the images the Owner made, by their file names

Spec §6.1 (source: "imports an image made elsewhere, a first-class path"), §10.5 and §14 (M6). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md).

## The gap

Each image the Owner makes in the image model's UI is downloaded, then imported with `kiripix import <id> <file>` or
`extend <id> add <file> --side …`, one at a time, with the right ID typed each time. For a district, that's dozens of
commands.

## What to build

- `kiripix inbox [--folder <path>] [--dry-run]` reads every PNG and JPEG in the inbox folder: `[inbox] folder` in
  `kiripix.toml` (a new section: a `schema_version` bump and its migration; default `inbox/` in the Project).
- **Matching by name** ([0349](0349-m6-to-paint-pack.md)'s return names): `<room>.png` or `<room>-<anything>.png` is imported
  as a Variant of `room.<room>`; `<room>.<side>.png` is `extend add` on that side. The Asset is named with or without its
  Kind prefix. A name that matches no Asset, or several, is left in place and listed (`inbox.unmatched`, `inbox.ambiguous`).
- **After each import** the file moves to `<folder>/imported/<date>/`, atomically, so a second run never imports it twice. A
  failed `extend add` (registration missed) leaves the file in place with that Command's finding.
- **No picks:** importing never picks. The result says which rooms now have exactly one Variant, with the `pick` command, so
  a session may pick a lone Variant (spec §6.1).
- `--dry-run` lists what would happen and changes nothing.
- Long runs check the cancel token between files.

## Acceptance criteria

- [ ] CLI seam: a folder with a room's image, a side piece of a room mid-`extend`, an unmatched file and an ambiguous one:
      two imports, two files moved, two findings; a second run imports nothing.
- [ ] CLI seam: the old `kiripix.toml` migrates and gains `[inbox]`.
- [ ] `inbox` has a sample in `tests/cli/test_contract.py`; spec §4 and §10.5 updated.
