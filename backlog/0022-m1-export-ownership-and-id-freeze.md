---
status: todo
milestone: M1
agent: godot-export
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0021-m1-room-export-and-manifest.md]
---

# M1: `--force`, `--adopt`, `--dry-run`, the ID freeze and Exit pairing

Spec §6.1 (Exit pairing), §9 (the Manifest) and ADR 0003. User stories 25–27 of [0010](0010-m1-room-end-to-end.md).

## What to build

- `export --force` backs up a changed owned file to `.kiripix/backups/<timestamp>/` and overwrites it. `--adopt` does
  the same for an unmanaged file already at a target path. `--dry-run` writes nothing, and lists what would be written
  and the two conflict cases separately. A refusal's finding is an `owner_action` naming the flag, because
  overwriting the game's edits is the owner's call.
- The ID freeze: once an ID is exported, renaming or removing it (a Marker ID, or a node name derived from a Mask)
  fails at `check` and at export, with the old ID and where it was exported. Adding IDs is always fine, and before the
  first export renames are free.
- `kiripix export --all`.
- Exit pairing as a Project check, through the hook from [0014](0014-m1-check-and-preview.md): every Exit names an
  existing room and Exit ID that points back. `check --all` and `export --all` fail on it; a single-room export only
  warns.

## Acceptance criteria

- [ ] `--force` and `--adopt` each leave the backup and the new file; `--dry-run` writes nothing.
- [ ] Renaming an exported Spawn fails with the frozen-ID finding; adding a second Spawn exports.
- [ ] Two rooms whose Exits point at each other pass `check --all`; removing one side's Exit fails it, and a
      single-room export of the other room only warns.
