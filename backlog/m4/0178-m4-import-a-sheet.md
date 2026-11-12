---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0174-m4-sprite-kind.md
---

# M4: `kiripix import --role sheet`: a sprite's PNG sheets and ZIPs

Spec §4 (`src/`, immutable) and §10. Part of [0174](0174-m4-sprite-kind.md). The `sprite` Kind itself is
[0179](0179-m4-sprite-recipe.md); this ticket is the import and what core needs to know of it. Read the trial's naming rule
([0175](0175-m4-sprite-pixellab-export-trial.md)) if it's done; the safety rules below don't depend on it.

## What to build

- `import <id> <file> --role sheet` for an Asset of Kind `sprite` (and only a sprite: another Kind gets
  `import.role_needs_sprite`). A PNG or a ZIP, stored by its hash in `src/sheets/`, with its original name in `imported.jsonl`
  as for other imports. Nothing is unpacked into `src/`.
- **A ZIP is checked at import, and refused whole** (`import.sheet_invalid`, naming the entry) when an entry's path is absolute,
  contains `..` or a drive, is a link, isn't a PNG by its bytes, or when the archive holds more than 4,096 entries or
  unpacks to more than 256 MB. Nothing is written when it's refused.
- `kiripix show <id>` lists the sheets, with each one's name, size, and for a ZIP its PNG count.
- A sprite takes no `--role variant` and no Pick; `import` without `--role` on a sprite means `sheet`.
- The import result (`data`) names the sheet, as it names a Variant. The `describe` text and the contract sample.

The Kind registration, the `frames` Stage and its reading of the ZIP are 0179's. Until 0179 lands, test this against the test
Kind `demo` with a `sheet` role, through `KIRIPIX_TEST_RECIPES`, or land it together with 0179's Kind stub, whichever is
smaller.

## Acceptance criteria

- [ ] CLI seam: a PNG and a ZIP import; the same file twice is one sheet; each refusal above (a `../` entry, an absolute path, a
      JPEG renamed `.png`, too many entries) leaves `src/` untouched, with exit code 1 and the finding's code.
- [ ] `--role sheet` on a room or a character is refused with `import.role_needs_sprite`.
- [ ] Contract samples for the changed `import` and `show`.

Budget: 100–150k tokens.
