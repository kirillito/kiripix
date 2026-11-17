---
status: todo
milestone: M5
agent: godot-export
type: ticket
parent: 0253-m5-icon-kind.md
depends_on: [0262-m5-icon-kind-and-stages.md]
---

# M5: export an icon

Spec §9. Part of [0253](0253-m5-icon-kind.md).

## What to build

- The icon's `export` Stage leaves `icon.png` and `icon.json` (`schema_version`, `asset`, `size`) in `out/export/`.
- The Exporter writes them to `icons/<name>.png` and `icons/<name>.json` under the export root, in the Manifest. No scene: the
  game's inventory UI loads the texture. The icon's ID is its Asset ID, frozen once exported, as any Asset's.
- `export --all` exports icons, and `--prune` removes a deleted one's files (with their `.import`, after
  [0250](0250-m5-m4-gate-small-findings.md)).

## Acceptance criteria

- [ ] CLI seam: an icon exports both files, listed in the Manifest. A second export with nothing changed writes nothing.
- [ ] Spec §9 gets an Icon row.
