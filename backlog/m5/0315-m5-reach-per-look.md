---
status: done
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0254-m5-looks-markers-combining-and-reach.md
depends_on: [0314-m5-look-markers-on-place.md]
---

# M5: `reach` per Look

[ADR 0013](../../docs/adr/0013-a-look-has-its-own-markers-collision-and-reach.md), decision 3. Part of
[0254](0254-m5-looks-markers-combining-and-reach.md). Spec §6.1 (`reach`).

## What to build

- **The graph:** `reach` gains `looks` upstream. A Look edit makes `reach` stale.
- **Per Look with its own `solid`:** flood the room's Spawns and Exits (crossing Links, as the room's flood does) over the
  Look's walkable from 0314's `looks/<look>/walkable.png`, and write `looks/<look>/reachable.png`. A Look's own Markers
  aren't reach targets. The flood checks the cancel token between Looks.
- **`report.json` schema 1** (it has none today; a file without one is refused, naming the rebuild). It gains `looks`: per
  such Look, its `markers`, `main`, `islands` and `areas`, as the room's are. Each of the room's islands and walkable areas
  gains `looks`, the Looks that reach it.
- **Findings:**
  - `reach.island_under_look` (info): a room island some Look reaches, naming the Looks. It replaces
    `reach.unreachable_island` for that island.
  - `reach.look_island` (warning): ground that only a Look makes walkable, and that it doesn't reach.
  - `reach.look_cuts_off` (info): a room Spawn or Exit unreachable under a Look.
  - `area.not_reached` drops to info when a Look reaches the area.
- **Versions:** `reach` 2 → 3.
- Spec §6.1: the `reach` row's outputs and findings.

## Acceptance criteria

- [x] CLI seam: a room whose yard sits behind a wall, with a Look that erases the wall, reports the yard as
      `reach.island_under_look` (info) naming the Look, not `reach.unreachable_island`, and exits 0.
- [x] `report.json` has `schema_version` 1 and `looks.<look>` with `main` and `islands`; the room's island lists the Look.
      `looks/<look>/reachable.png` exists. A Look without its own `solid` has no entry.
- [x] A Look that adds ground it doesn't reach gives `reach.look_island` (warning); a Look that walls off a Spawn gives
      `reach.look_cuts_off` (info).
- [x] An older `report.json` is refused, naming the rebuild. Editing a Look makes `reach` stale.
- [x] The laneway's `back_gate_open` (M4 gate room, checked by hand in the Result): the yard is info under the Look. (Checked on a copy: see Result.)

## Result

- **Built.** `reach` has `looks` upstream (a Look edit makes it stale). For each Look whose `looks.json` record has a `solid`,
  it floods the room's Spawns and Exits, crossing Links, over `place/looks/<look>/walkable.png` (dash against the Look's own
  `solid`) and writes `work/reach/looks/<look>/reachable.png`. A Look without its own `solid` has no entry. The flood checks
  the cancel token between Looks. `report.json` is schema 1 (`schema_version`, and `looks.<look>` with `markers`, `main`,
  `islands`, `areas`); each room island and area gains `looks`, the Looks that reach it; each island of a Look gains `added`,
  its spots the room doesn't walk. An old `report.json`, with no `schema_version`, is refused, naming
  `kiripix run <asset> reach --force`. `reach` now also checks `markers.json`'s schema.
- **Findings.** `reach.island_under_look` (info) replaces `reach.unreachable_island` for an island a Look reaches;
  `reach.look_island` (warning) for a Look's island with `added` spots; `reach.look_cuts_off` (info) for a Spawn or Exit the
  room reaches and a Look doesn't; `area.not_reached` is info when a Look reaches the area.
- **Versions.** `reach` 2 to 3. `report.json` has schema 1 (new).
- **Op.** `walkable_island_labels` (`kiripix/ops/reach.py`), which `walkable_islands` now calls: the islands and a label grid.
- **Spec.** §6.1: the `reach` row, and the notes that said `reach` reads the room without its Looks.
- **Tests.** `tests/cli/test_reach_looks.py` (one test per criterion, and an area one); a golden-seam test for the new Op.
- **The laneway, by hand.** On a copy of `room.ch01_002_laneway` (the art Project left untouched), `kiripix run
  room.ch01_002_laneway` rebuilt `place` and `reach`: the yard at (58, 345), 463 x 274, is `reach.island_under_look` (info),
  naming `back_gate_open`. The other five islands stay `reach.unreachable_island` warnings. Before a rebuild, `kiripix show`
  on that room fails with `internal.error` on the old `markers.json` (schema 1), where it should refuse it as a finding.
  **Fixed (main session, 2026-11-19):** `AssetGraph.check` (`kiripix/core/graph.py`) turns a Check's `StageFailure` (an
  output it can't read, such as one from an older Kiripix) into a `stage.output_unreadable` finding, an error with the
  rebuild as its `fix` (`kiripix run <asset> <stage> --force`), so `check` exits 2, not 1 with `internal.error`. Re-checked
  on a fresh copy of the laneway: `show` is ok and `check` reports `stage.output_unreadable`. Test:
  `tests/cli/test_show_old_output.py`; the old-file tests in `test_look_markers.py` and `test_reach_looks.py` now expect it.
