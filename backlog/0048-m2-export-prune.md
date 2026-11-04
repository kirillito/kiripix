---
status: todo
milestone: M2
agent: godot-export
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: `export --prune`

Spec §9 (Deleting an asset) and ADR 0003. Story 15 of [0037](0037-m2-layers-and-props.md). Follows D11 in [0037](0037-m2-layers-and-props.md).

## What to build

- `--prune` on `export`, with the surface D11 settles. A Manifest under `<root>/manifest/` whose Asset isn't in the Project
  is a deleted Asset.
- Under the same hash rule: a file whose hash matches is removed. A mismatch refuses with `export.file_changed`, naming the
  file, unless `--force`, which backs it up first. Plan before writing, as `export_assets` does, so a refusal changes nothing.
- The Manifest goes last, so a stopped prune can run again, and a listed file already gone is fine. Empty folders under the
  export root go too. `.import` sidecars stay ignored (ADR 0003).
- A warning finding if another room's Exit still names the pruned Asset.
- `--dry-run` lists what would go and what would be refused. `ExportData` gains `removed` and `would_remove`.
- Holds the project lock. Don't touch an existing Asset's files.

## Acceptance criteria

- [ ] Delete an exported Asset's folder, then prune: its files and Manifest are gone, and another Asset's are untouched.
- [ ] Without `--prune`, the files stay.
- [ ] An edited file refuses with nothing removed; `--force` leaves it in `.kiripix/backups/<timestamp>/`.
- [ ] `--dry-run` removes nothing, and lists both cases.
- [ ] A file not in the Manifest, beside the pruned files, is left alone.
- [ ] `tests/cli/test_contract.py` still passes with the changed output.
