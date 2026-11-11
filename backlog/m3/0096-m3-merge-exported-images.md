---
status: done
milestone: M3
agent: godot-export
type: ticket
---

# M3: a branch merge conflicts on the exported images

Spec §9 (Branch merges). Found at the [M2 gate](../m2/0058-m2-gate.md), in a real two-branch merge of a clone of the game: the Manifest merge
driver resolved the Manifest (counter 2 and 2 became 3, ours in `files`, theirs in `replacing`), but `sprite.png`, exported on both
branches, conflicted, because git can't merge a binary. Someone had to pick a side with `git checkout --ours` before the commit. The
next export then wrote the sprite with no refusal, so either side would have done.

## What to build

- The exported images under the export root resolve without a conflict, since the Manifest already accepts either side and the next
  export rewrites them. For example, `manifest install` also writes a `merge=ours` rule for the export root's `*.png` (the built-in
  `ours` driver, configured in the clone), so a merge keeps our image and the next export puts the right one in place.
- The same for generated `.tscn` and `.tres` files, if they can conflict the same way.
- Export's existing check of the driver also checks these rules, and its `fix` installs them.
- The spec's §9 says what happens to the images in a merge.

## Acceptance criteria

- [x] A real `git merge` in a temporary repo with the driver installed: two branches export one Asset with different images, the merge
      finishes with no conflict, and the next export is clean.
- [x] Without the image rules, export warns with the `fix`.

## Findings

- `manifest install` writes `*.png`, `*.tscn` and `*.tres` `merge=kiripix-ours` to `<root>/.gitattributes` (keeping the game's own lines) and sets `merge.kiripix-ours.driver = true` in the clone. A separate driver name avoids clashing with a `merge.ours` the game may define. The existing check (`export.merge_driver_missing`) now also probes these rules with `git check-attr` and the config; its `fix` is still `kiripix manifest install`.
- The scenes conflicted too (the old test asserted `alley.tscn` stayed conflicted); they now keep ours. The real-merge test finishes with no conflict, and the next export, after the Project has both branches' Markers, is clean.
- Owner: re-run `kiripix manifest install` in the game clone, and commit the new `<root>/.gitattributes`. Until then export warns.

## The Owner's decision (2026-11-07)

The `merge=kiripix-ours` rule covers the exported `.tscn` and `.tres` files as well as `.png`. A hand edit to an exported scene
on the other branch is dropped in a merge without a conflict. The Owner keeps it so: game logic lives in scenes that instance
Kiripix's scenes, never inside them (spec §2, principle 10), so an exported scene has no hand edits to lose.
