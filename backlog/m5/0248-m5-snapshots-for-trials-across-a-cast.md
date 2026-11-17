---
status: done
milestone: M5
agent: core-engineer
type: ticket
parent: 0236-m5-the-games-next-needs.md
---

# M5: compare settings across a cast: `set` on several Assets, snapshots and the cast sheet in rows

Spec §10 (Probes). Part of [0236](0236-m5-the-games-next-needs.md), item 14. Builds on the cast sheet
([0226](../m4/0226-m4-cast-sheet-probe.md)).

## The gap

The art repo's `chargen/to_kiripix.py` wraps Kiripix to compare settings across many characters. It does three things:

- runs a Stage with overrides (`--set finish.inner_lines=outline`);
- keeps each run's export under a label (`--snap`);
- lays the labels side by side with `contact_sheet.py`.

The game's 0088 ran five such passes over 16 characters. The next trial shouldn't need the script.

## Decided here (the Owner may overturn it)

Settings still change only through `set`, so they stay recorded and every rebuild is the normal one. Kiripix doesn't get a
second, unrecorded way to run with other parameters. What it lacks is cheap: setting many Assets at once, and keeping what was
built so it can be compared.

## What to build

- **`set` on several Assets:** `kiripix set <id,id,...> <stage> key=value...` sets each, as one Command call. The result
  lists each Asset's new params and states. It all applies, or none does, if one refuses.
- **`kiripix snapshot <id,id,...> --label <label>`:** copies each Asset's built `sheet` outputs (`sheet.json`, the colour
  atlas) into `.kiripix/snapshots/<label>/<id>/`, with the parameters of every Stage they were built from, and a note of
  which Stages were stale. It records nothing in the Project, so it's a Probe. `--label` is a snake_case name, and an
  existing label needs `--replace`.
- **`cast-sheet ... --snapshots <label,label,...>`:** one row per label, the same Assets in the same order, each row titled
  with its label and the parameters that differ between rows. Without `--snapshots`, the sheet is today's.
- `kiripix snapshot --list`, and a way to drop a label.

## Acceptance criteria

- [x] CLI seam: `set` on two characters changes both. A bad value on one changes neither.
- [x] Two snapshots under two labels give a cast sheet with two rows. The JSON names the differing parameters.
- [x] A snapshot of an unbuilt Asset is a finding, and the others are kept.
- [x] Contract samples for `snapshot`. Spec §10 lists it.

## Result (2026-11-16)

- **`set <id,id,...> <stage> key=value...`**: one Command call. `editing.set_params_many` checks every Asset first and
  writes only if all pass, so one bad Asset (an unknown ID, a bad value) changes none; the findings of all the refusing
  Assets come together. Core takes the Asset locks (new `LockNeeds.assets`, taken in core's fixed order). The result keeps
  the single-Asset shape (`asset`, `params`, `stages`); with several, `asset` is the IDs joined and `assets` lists each
  one's `params` and `stages`.
- **`kiripix snapshot <id,...> --label <snake_case>`** (a Probe; `kind="probe"`, no lock, nothing in the Project): copies
  `sheet.json` and the colour atlas to `.kiripix/snapshots/<label>/<id>/` with `snapshot.json` (`schema_version`, the
  parameters of the `sheet` Stage and every Stage upstream of it, and the Stages that weren't current: also a
  `snapshot.stale` warning). An Asset with no built sheet is a `snapshot.not_built` warning and left out, the others are
  kept; if none is kept, `snapshot.empty` (exit 1) and no label is created. An existing label needs `--replace`
  (`snapshot.label_exists`); `--replace` replaces the given Assets' entries and keeps the label's other Assets. Each entry
  is built beside its place and swapped in. `--list` gives the labels and their Assets; `--drop <label>` deletes one.
  A Kind without a `sheet` Stage is `snapshot.no_sheet`.
- **`cast-sheet --snapshots a,b`**: one row per label, the same Assets in the same order, read from the snapshots (not the
  current sheets). Each row has a title strip: the label and its value of every parameter that differs between the labels
  (`mixed` when the Assets in the row differ). JSON adds `rows` (label, title, y, height, `ground`), `differing` (stage,
  param, values by label then Asset) and `row` on each cell; each cell's pivot is on its own row's ground line. Findings:
  `cast.not_snapshotted` (an Asset a label lacks: left out of that row), `cast.snapshot_stale`; an unknown label is
  `snapshot.unknown_label`. Without `--snapshots` the sheet is as before.
- Work in `kiripix/core/snapshots.py`, `kiripix/core/cast.py`, `kiripix/core/editing.py`, `kiripix/commands/decisions.py`,
  `kiripix/commands/probes.py`, `kiripix/commands/registry.py`, `kiripix/commands/invoke.py`. Tests:
  `tests/cli/test_snapshots.py` (18) and a contract sample for `snapshot`. Spec §10's command list updated.

### The Owner's choices (2026-11-17)

- `snapshot --replace` replaces only the given Assets' entries and keeps the label's other Assets.
- `set` on one Asset keeps its old result. On several, `asset` is the IDs joined by commas and `assets` lists each one's
  `params` and `stages`.
- **Known gap:** a snapshot records the parameters as they are when it's taken. After `set` without a rebuild, they aren't the
  ones the sheet was built with; `snapshot.stale` and `cast.snapshot_stale` warn. Rebuild before a snapshot (`run <ids>`).
