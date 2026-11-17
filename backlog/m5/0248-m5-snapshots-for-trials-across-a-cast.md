---
status: todo
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

- [ ] CLI seam: `set` on two characters changes both. A bad value on one changes neither.
- [ ] Two snapshots under two labels give a cast sheet with two rows. The JSON names the differing parameters.
- [ ] A snapshot of an unbuilt Asset is a finding, and the others are kept.
- [ ] Contract samples for `snapshot`. Spec §10 lists it.
