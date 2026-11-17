---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: the M4 gate's small findings

Found at the M4 gate ([0142](../m4/0142-m4-gate.md), "Gate findings, not fixed"), 2026-11-16. The larger ones have their own
tickets: [0232](0232-m5-look-edit-of-a-piece-or-crop.md), [0235](0235-m5-settings-writes-keep-comments.md), and the yard
behind the back gate in [0254](0254-m5-looks-markers-combining-and-reach.md).

## What to fix

1. **`kiripix new --help`** says a Kind is "room, prop or character". Take the list from the registry of Kinds, so `sprite`
   (and `portrait`, from 0242) appear without another edit.
2. **`export --prune` leaves Godot's `.import` files** beside the PNGs it removes, and so the folder. Remove a pruned PNG's
   `.import` sidecar with it, under the same backup, and then the folder if it's empty. Godot regenerates `.import`, so the
   Manifest still doesn't own it: remove only the sidecar of a file it pruned.
3. **`exit.no_room` is an error in `check` and a warning in `export`.** Make the two agree on one severity. A single-room
   export only warns, by spec §6.1 ("Exit pairing is a Project check"), so `check <id>` should warn too, and `check --all`
   is where it's an error. Say so in the finding.
4. **A forced Stage doesn't rebuild the Stages after it.** Status hashes inputs, not outputs. After a code fix,
   `run <id> palette --force` left `finish`, `sheet` and `export` `done` on the old output, and each had to be forced in
   turn. Add `run <id> --force --from <stage>`: force that Stage and every Stage after it in the recipe. Keep plain
   `--force` as it is.

## Acceptance criteria

- [ ] CLI seam, one test per item: `new --help` lists every registered Kind; a prune removes the `.import` and the empty
      folder; `check <id>` and `export <id>` give `exit.no_room` the same severity; `run --force --from palette` rebuilds
      `palette` to `export`.
- [ ] Contract sample updated for `run`'s new flag. Spec §9 (Manifest, deleting an asset) and §10.5 updated.
