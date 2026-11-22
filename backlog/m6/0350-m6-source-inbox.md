---
status: done
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

## Result

`kiripix inbox [--folder <dir>] [--dry-run]` (`kiripix/commands/inbox.py`; all logic in `kiripix/core/inbox.py`, which uses
`sources.import_file`, `extend.add_piece` and the new `extend.ensure_canvas`). Locks: the project lock, and each Asset's lock
for the length of its import.

- **Settings:** `[inbox] folder` (default `inbox`, relative to the Project), `schema_version` 10, pure migration 9 to 10
  (`_add_inbox_section`; the default is read, nothing written). `kiripix init`'s template has the section.
- **Matching** (`inbox.parse`): lower-case file stem; a last dotted part of sides (`east`, `east+south`) makes it a piece; the
  rest up to the first `-` is the Asset's name, with or without its Kind prefix. Only Assets that take image Variants count
  (not characters or sprites). No match: `inbox.unmatched`; several (such as `room.crate` and `prop.crate`):
  `inbox.ambiguous`; both are warnings with an `owner_action`, exit 0, the file stays.
- **A piece** first gets its canvas record from `extend.ensure_canvas`: one the Owner wrote with `extend canvas` for the same
  sides on the same image is kept, else the canvas is written at the default keep. Then `extend add`. A refused piece
  (`extend.registration_missed`, exit 2) stays with that finding; the run goes on and ends with the worst exit code.
- **Filed** files move to `<folder>/imported/<date>/` (`os.replace`; a name taken there gets `.2` and so on). Nothing picks.
- **Result data:** `folder`, `dry_run`, `imported` (count; would-be with `--dry-run`), `left` (count), `files[]` (`file`,
  `outcome` imported|would_import|unmatched|ambiguous|failed, `asset`, `action` import|extend, `sides`, `variant`, `piece`,
  `created`, `moved_to`, `candidates`, `code`) and `lone_variants[]` (`asset`, `variant`, `pick`: the room has exactly one
  Variant and it isn't picked; filled only from rooms imported into in this run).
- No Stage's `version` changes. `schema_version` 9 to 10 changed the `schema_version = 9` expectations in nine CLI tests.
- Tests: `tests/cli/test_inbox.py`; samples in `tests/cli/test_contract.py` and `tests/cli/test_serve.py`; spec §4 and §10.5.


**Review fixes (2026-11-20):** `inbox --file <image> --asset <id> [--sides <side>]` files one image into one Asset, whatever its name, through the same `_file` (the canvas record, then `extend add`; or `import`), and doesn't move it: what the UI's drop runs (0351). `outcome` and `action` are Literal types. Left as built, on review: matching takes every Kind that takes an image Variant, not only rooms, because the ticket's own `inbox.ambiguous` ("several") only happens across Kinds; and a refused piece keeps the canvas record `inbox` wrote, which is the canvas `to-paint` packed (default keep), so the next try uses it.
