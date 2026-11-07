---
status: todo
milestone: M3
agent: godot-export
type: ticket
---

# M3: a branch merge conflicts on the exported images

Spec §9 (Branch merges). Found at the [M2 gate](m2/0058-m2-gate.md), in a real two-branch merge of a clone of the game: the Manifest merge
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

- [ ] A real `git merge` in a temporary repo with the driver installed: two branches export one Asset with different images, the merge
      finishes with no conflict, and the next export is clean.
- [ ] Without the image rules, export warns with the `fix`.
