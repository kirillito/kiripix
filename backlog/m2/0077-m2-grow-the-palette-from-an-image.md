---
status: done
milestone: M2
agent: imaging-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: grow the Project's palette from an image

Spec §7 and §10. The Owner's draft palette has 64 colours, and they want more before the Layers trial
([0076](0076-m2-claude-layers-first-pass-trial.md)). Picking them by hand is slow. General tools count pixels and regenerate the
whole palette, which loses the named colours and spends new ones on JPEG noise.

The palette is for how a room looks. `flood`, SAM 2 and LaMa all work before the `palette` Stage (ADR 0004), so this doesn't
change flood or lifting, and its acceptance doesn't depend on them.

## What to build

Two Commands, so that an agent can suggest colours and only the Owner can add them.

**An Op, in `kiripix/ops/palette.py`:** given an image and a palette, it suggests up to N new colours. It's pure numpy with no new
dependency, and gives the same result every time for the same input.

- It clusters in OKLab, with the existing colours held fixed as clusters. New clusters start where the palette fits the image
  worst, so colours go to what's missing.
- A candidate within a minimum OKLab distance of an existing or chosen colour is dropped, so it may return fewer than N.
- Transparent pixels are ignored.

**`kiripix op palette-suggest <image> --add N`:** changes nothing in the palette, and an agent may run it.

- `--scale`, default 2.15 Source px per target px, downscales the image first, because the game never sees noise at full size. The
  default is the scale the Project's rooms use so far. It's a flag, not a setting.
- `--min-distance` overrides the minimum OKLab distance. Choose its default by testing on the image below, and state it in `--help`.
- `--palette` works as it does on the other `op` Commands. The default is the Project's.
- Under `.kiripix/`, it writes a proposal file with `schema_version`, the image's hash, the palette's hash, and the colours. Beside
  it, it writes a swatch and the downscaled image mapped through today's palette and through the palette with the new colours.
- The result gives the colours, the paths, and the mean OKLab error before and after.

**`kiripix palette-add <proposal> [--name <prefix>]`:** kind `owner-only`, as `accept` is, so without an interactive terminal or a
session it stops with `owner.required`.

- It appends the proposal's colours to the end of the Project's `.gpl` atomically, named `<prefix>-01` and so on, with a default
  prefix of `added`. Existing lines stay as they are, including names and comments, and their order doesn't change, because
  order breaks ties in nearest-colour mapping.
- If the palette's hash no longer matches the proposal's, it's refused with `palette.proposal_stale`, and the finding's `fix` is
  the `palette-suggest` to run again. A second add of the same proposal is refused the same way.
- The result names how many rooms this makes stale. It runs nothing and rebuilds nothing.

This ticket adds no UI. The spec's Command list gains both, and `.kiripix/` keeps these files out of the Project's tracked ones.

## Acceptance criteria

- [x] Golden seam: on a fixture, the Op gives the same colours every run, and none is within the minimum distance of another or of
      an existing colour.
- [x] A palette that already fits an image adds no colours, and says so rather than failing.
- [x] CLI seam: `palette-suggest` leaves `palette.gpl` byte-identical and every Asset's status unchanged.
- [x] CLI seam, under the harness's owner setting: `palette-add` keeps every existing line byte-identical and in order, and the
      file still passes `check_palette`.
- [x] Without the owner setting, `palette-add` exits 3 with `owner.required` and writes nothing.
- [x] A proposal made before the palette changed is refused with `palette.proposal_stale`.
- [x] After an add, a room's `palette` and later Stages are `stale`, with nothing in `needs-review`, and `run` rebuilds them.
- [x] Both Commands have samples in `tests/cli/test_contract.py`.
- [x] A manual check, not in CI, on `c:\Workspace\urban-mystery-club\references\subway-lower-bay.jpeg` with the art repo's palette:
      `palette-suggest --add 32` runs, its error falls, and its time is noted here. The image is only read, and no test depends
      on it. The Owner judges the previews and runs `palette-add`, or doesn't.

## Notes

- Manual check, done on `c:\Homespace\urban-mystery-club\references\subway-lower-bay.jpeg` (the path above says `Workspace`).
  The art repo's 64-colour palette was copied into a scratch Project, and the image was only read. It downscales to 640x357 at
  `--scale 2.15`. With `--add 32`, the mean OKLab error before is 0.0241. At the default 0.03 it suggests 15 colours, error
  0.0176 after; at 0.02, 29 colours and 0.0122; at 0.04, 8 colours and 0.0228. Each call took 13 to 27 s, measured while the
  test suite ran alongside, so alone it's faster. The default stays 0.03; `--min-distance 0.02` comes close to the 32 asked
  for. The Owner judges the previews and runs `palette-add`, or doesn't.
- Earlier, before the subway image was found: as a stand-in, `palette-suggest --add 32` ran on the game repo's `references/approved/ch01-dungeon-r01.jpeg` (402x566 after `--scale 2.15`) with the art repo's 64-colour palette, in a scratch Project, read-only. About 5 s per call (9 s while other tests ran). Mean OKLab error before 0.0338; after 0.0100 at `--min-distance 0.02` (26 colours), 0.0122 at 0.025 (23), 0.0136 at 0.03 (22), 0.0223 at 0.04 (10), 0.0255 at 0.06 (3).
- Default `--min-distance` is 0.03: the closest pair in the art palette is 0.032, so new colours are no closer than the old ones.