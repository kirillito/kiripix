---
status: done
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

- [x] `--force` and `--adopt` each leave the backup and the new file; `--dry-run` writes nothing.
- [x] Renaming an exported Spawn fails with the frozen-ID finding; adding a second Spawn exports.
- [x] Two rooms whose Exits point at each other pass `check --all`; removing one side's Exit fails it, and a
      single-room export of the other room only warns.

## Notes

- **Flags.** `--force` takes a file the Manifest lists that the game changed (`export.file_changed`). `--adopt` takes a
  file at a target path that the Manifest doesn't list (`export.file_unmanaged`). Neither does the other's job: `--force`
  on an unmanaged file, or `--adopt` on an edited one, still refuses. Each refusal is an `owner_action` that names its
  flag. A taken file is copied first to `.kiripix/backups/<UTC timestamp>/<game folder name>/<path under res://>`; one
  folder per call, shared by every Asset of `--all`. A file that already holds the very bytes export would write isn't
  backed up. `--dry-run` writes nothing, not even a backup; its refusals are `warning` findings (exit 0) and the data lists
  `would_write`, `changed`, `unmanaged` and `backed_up` (what `--force`/`--adopt` given with it would back up).
- **Plan, then write.** `export_assets` plans every Asset before it writes any file, so a refusal anywhere (not built, a
  frozen ID, a refused file) leaves the game untouched. Not built stays `export.not_ready`; a refusal's exit code is the
  worst of the Assets'.
- **Result shape.** `ExportData` gained `asset` (null with `--all`), `dry_run`, `would_write`, `backed_up`, `changed`,
  `unmanaged` and `assets` (one entry per Asset with its `written`, `unchanged`, `manifest` and `counter`). The top-level
  lists are the union over Assets; `manifest` and `counter` are null with `--all`. In a dry run `counter` is the one the
  export would leave.
- **The freeze** (`export.id_frozen`, an error, no `fix`: the Owner decides to put the ID back). Compared with the game's
  Manifest: Marker IDs come from the Decisions, not the built output, so a rename fails `check` at once, before `run`.
  Masks and Layers come from the built `room.json`, if there is one. With no game configured, or no Manifest for the
  Asset, nothing is frozen. With a game configured but not at its path, `check` fails with `export.no_project` rather than
  guess (spec §9, ADR 0003). `--force` and `--adopt` don't lift it. Undoing a rename
  brings the ID back, so that is the way out.
- **Within the import rule.** `check` (a Command) can import `kiripix.export`, which is above core. Single-Asset `check`
  calls `frozen_findings` itself. `check --all` gets the freeze and Exit pairing through core's Project check hook:
  `kiripix/export/checks.py` registers one when `kiripix.export` is imported, and every Command that checks imports it.
  Core never imports export.
- **Exit pairing** (`kiripix/export/checks.py`). Read from the Decisions. `exit.no_room` (no such room), `exit.no_exit`
  (the room has no such Exit), `exit.not_paired` (it has, but that Exit leads elsewhere). All errors in `check --all` and
  `export --all`; `warning` for one room's `export <id>` (only that room's own Exits). A single-Asset `check <id>` doesn't
  run pairing.
- **`export --all`** exports every Asset of a Kind with an exporter (rooms), in ID order, under the project lock and every
  room's lock. It refuses on Exit pairing before it plans anything.
- **After a room is ready.** `next <id>` names `kiripix export <id>` until the game has what is built, then reports `done`.
  `check --all` runs every Asset's Checks, the freeze and pairing, and passes with no findings. `export --all` a second time
  writes nothing and leaves the counters.
