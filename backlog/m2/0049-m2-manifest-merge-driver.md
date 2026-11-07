---
status: done
milestone: M2
agent: godot-export
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: the Manifest merge driver and `manifest repair`

Spec §9 (Branch merges) and ADR 0003. Story 16 of [0037](0037-m2-layers-and-props.md). Follows D12, D13 and D14 in [0037](0037-m2-layers-and-props.md).

## What to build

- `kiripix manifest merge <base> <ours> <theirs>`, a Command in a `manifest` group, like `runners`. Git runs it from the game's
  repo, so it needs no Kiripix Project, takes no locks, and takes its paths as given.
- The rule: counter = the higher + 1. IDs: the union, since an ID frozen on either branch stays frozen. `exported`: either.
  `files` per D12. It writes `<ours>` atomically, and exits 0. On a Manifest it can't read or a newer `schema_version` it
  leaves `<ours>` alone and exits 1, so git keeps the conflict.
- The install and the check, per D13: export gives a warning finding whose `fix` installs the driver, when the game is a git
  repo without it. It says nothing when the game isn't a git repo or git is missing.
- `kiripix manifest repair`, per D14, under the project lock. `read_manifest`'s refusal names it when a Manifest has conflict
  markers, as a `fix`.

## Acceptance criteria

- [x] A real `git merge` in a temporary repo with the driver installed: two branches export one Asset, the Manifest merges
      with no conflict, counter = higher + 1, IDs the union.
- [x] Without the driver, export warns with a `fix`; running it, then exporting again, gives no warning.
- [x] `.gitattributes` alone (no config) still warns.
- [x] A Manifest with committed conflict markers: `export` refuses and names `manifest repair`; after it, `export` works.
- [x] An unreadable side exits 1 and leaves the file unchanged.
- [x] Samples for each new Command in `tests/cli/test_contract.py`.
