---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0127-m4-room-looks.md
---

# M4: a Look's edit Variants: `import --look` and `pick --look`

Spec §4, §6.1 (Looks) and §10.5; ADR 0009.

## What to build

- `kiripix import <id> <png> --look <look>` stores an edit Variant under `src/looks/<look>/<hash>.png`. That is outside
  `source`'s `src/*.png`, so the room's `source` Stage stays `done`. JPEG converts to PNG, as `import` does now. Refused on a
  non-room Asset and on a room with no picked Source.
- `kiripix pick <id> <variant> --look <look>` records a `pick` Decision in the `looks` journal, with the room Source's
  hash at that moment. One Variant needs no judgement, so an agent may pick it, as for a room's Source.
- The `looks` Stage's inputs include `src/looks/**`, so a new edit makes `looks` stale and nothing above it.
- A pick whose Source hash isn't the current Source's doesn't apply: `needs-input` with the reason "the edit was made
  on another Source", and an `owner_action` to re-make it.
- `describe room` lists the new options.

Coordinate with [0130](0130-m4-looks-stage.md), which declares the Stage. This ticket can land first, with the Stage
declared and a build that does nothing.

## Acceptance criteria

- [x] At the CLI seam: `import --look` adds a Variant, and `status` shows `source` still `done` and `looks` stale.
- [x] Re-picking the room's Source puts `looks` in `needs-input` with that reason.
- [x] Samples in `tests/cli/test_contract.py` for the changed inputs.

## Result

- **`import <id> <png> --look <look>`** stores the edit as `src/looks/<look>/<hash>.png` (JPEG converts to PNG; the name is
  recorded in `imported.jsonl` as for a Source). Refused with `import.look_needs_room`, `import.look_needs_source` (a `fix` when
  the room has one Variant to pick, else an `owner_action`), `import.look_takes_images` (`--role` other than `variant`) and
  `look.invalid_id`. A Look ID is a Marker-style ID (`door_shut`, `circuit.hall`), since it is a folder name.
- **`pick <id> <variant> --look <look>`** records `pick` with `{look, variant, source}` in the `looks` journal, `source` being the
  room's picked Source's Variant name at that moment (`pick.look_needs_room`, `pick.look_needs_source`, `pick.unknown_variant`).
- **The `looks` Stage** is declared in the room Recipe after `palette`, before `place`, with a build that does nothing (no Looks:
  `done`). Inputs: files `src/looks/**/*.png`; upstream `palette`, `source`, `fit`, `layers`, `masks`; setting `palette`. Its only
  Decision so far is `pick` (`LOOK_PICK`). `place`, `reach` and `export` don't read it, so a new edit makes `looks` stale and
  nothing above it. The Stage's code is in `kiripix/recipes/looks.py`.
- **`needs_input`:** a pick whose `source` isn't the room's current Source gives needs-input, "the edit was made on another
  Source", with an `owner_action` naming the Looks to re-make; so does a picked edit whose file is gone.
- **For 0130:** `StageRun.upstream_decisions` (new, filled by core from the upstream Stages' journals) is how a Stage reads what an
  upstream Stage was told; `looks` uses it for the room's current Pick. 0130 adds `look`, region and `solid` Decisions, fills
  `run_looks`, and widens `needs_input` as it needs. `export` doesn't depend on `looks` yet; 0131 adds it (and the stale `export`
  ADR 0009 mentions).
