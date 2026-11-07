---
status: done
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
---

# M1: a `done` `export` Stage reads as "exported"

Found by the agent acceptance test ([0028](0028-m1-agent-acceptance-test.md)), real run of 2026-11-04:
[docs/acceptance/2026-11-04-m1-4.md](../../docs/acceptance/2026-11-04-m1-4.md), 10,697 fresh tokens.

## The bug

Once every Stage is built, `status` and `show` read `export done`, and `run` exits 0. Nothing has reached the game yet:
the `export` Stage only builds engine-free outputs in `out/export/`, and `kiripix export` writes the Godot files (see the
notes of [0021](0021-m1-room-export-and-manifest.md)). `check --all` passes too, because a room that isn't in the game
fails nothing.

The agent ran `run`, `check --all` and `status`, saw only `done` and a clean Check, and closed with "The room is exported
and `kiripix check --all` passes". The harness's own verification found all three game files missing.

Only `next` says otherwise: "export is done (the game doesn't have what is built yet)", naming `kiripix export room.alley`.
The agent didn't ask `next` again, and nothing it did ask pointed there. Run 3 did run `export`, so this is intermittent,
as the Pick was before [0033](0033-m1-source-stage-contradicts-next-on-the-pick.md).

## Notes

- **What changed:** a `run` that exits 0 and leaves an Asset fully built with something the game doesn't have carries the
  `info` finding `export.pending`, with `fix: kiripix export <id>`. Its exit code stays 0. `status` and `show` have a field
  `export_command`, and print the same Command in their text.
- **Derived, never stored** (ADR 0005): `kiripix.export.export_command` works it out from the Stages and the Manifest on
  every call.
- **Fully built, not necessarily exportable.** `status` and `show` don't run Checks, so a built room with a failing Check
  still names `export`, which then refuses and says why. `run` doesn't, because such a run exits 2. So does a `run --all`
  with any failure, even for the rooms that are ready.
- **`check` is unchanged.** Not being in the game fails no Check, and `check --all` stays clean.

## Acceptance criteria

- [x] After a `run` that leaves a room fully built and not in the game, the `run` result and `status` both name
      `kiripix export <id>`.
- [x] Once exported, neither says so, and an edit that changes the output brings it back.
- [x] A CLI test covers it, and the next real acceptance run reaches `export`
      ([2026-11-04-m1-5.md](../../docs/acceptance/2026-11-04-m1-5.md): one run, so later runs will show whether it holds).
