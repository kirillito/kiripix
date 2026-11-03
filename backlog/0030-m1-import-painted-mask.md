---
status: todo
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0016-m1-masks.md, 0023-m1-serve.md, 0032-m1-rest-transport-and-multipart.md]
---

# M1: a Command to import a painted mask image

Spec §4 (importing a painted mask image) and §10.5. A follow-up to [0016](0016-m1-masks.md), which added the `import`
Decision to the room's `masks` Stage but no way to store its image.

## Background

The `import` Decision's data is `{"png": <sha256>}`. It names a painted PNG at `decisions/imports/<hash>.png` in the
Asset's folder, and the Stage splits it into one 1-bit Mask per name (the nearest defined colour, plus the `import`
table). No Command writes that file. Today the tests place it by hand and then `decide`.

## What to build

- A writing Command that takes an Asset and a PNG, copies the PNG to `decisions/imports/<hash>.png` (atomic, named
  by its hash, so a second import of the same file stores nothing new), and records the `import` Decision on the
  `masks` Stage through the Decision journal, like `override` does for Overrides. It refuses a file that isn't a PNG,
  and an Asset whose Kind has no `masks` Stage, with findings.
- The name is open: `kiripix mask-import <id> <png>`, or a `--png` option on `decide` that stores the file and fills
  in the hash. Pick one, and add it to the CLI list in spec §10.5.
- Over REST the PNG is a multipart part of the Command's own request, as for `override`
  ([0032](0032-m1-rest-transport-and-multipart.md)).
- A sample in `tests/cli/test_contract.py`.
- Switch the 0016 tests in `tests/cli/test_masks.py` that place the PNG by hand over to the new Command.

## Acceptance criteria

- [ ] Importing a painted PNG and then `run` gives the split Masks; `undo` removes the Decision and `run` empties them.
- [ ] Importing the same file twice stores one PNG under `decisions/imports/`.
- [ ] A non-PNG file, and an Asset without a `masks` Stage, are refused with a finding and exit code 1.
