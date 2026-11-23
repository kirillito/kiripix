---
status: done
milestone: M6
agent: core-engineer
type: ticket
---

# M6: `extend add` joins a piece whose kept strip the image model re-rendered

Spec §14 M4 (`extend`) and the `kiripix.toml` block (§4). The Owner is moving room painting from Nano Banana to GPT Image
(2026-11-23).

## The problem

GPT Image always re-renders the whole canvas, kept strip included; it can't leave pixels untouched. On a real piece (the game
repo's `room.annex_laneway`, its east piece, canvas written with `--side east --keep 420,234`), `extend add` refuses it with
`extend.registration_missed`: "the edge patches are 0.66 px from the fit, over the 0.5 px limit". The limit was
`MAX_RESIDUAL = 0.5` in `kiripix/checks/join.py`, used by `add_piece` in `kiripix/core/extend.py` and by the join Check.

The re-rendered strip is the same picture: best whole-pixel shift (0, 1), per-channel gain 0.993 / 0.998 / 1.011, a mean
difference of about 10/255 from re-rendered texture. A scratch join doing the same steps (shift, gain, least-difference seam)
gave a seam with a mean difference of 2.7/255 and no seam visible at 2x on the roof, the doors, the asphalt or the gravel. The
join works; only the gate is too strict for this kind of model.

The piece also came back 1679 x 937 for a 1678 x 937 canvas.

## What to do

1. The registration limit is a Project setting, `[extend] max_residual` (px, default 0.5, so existing rooms and tests are
   unchanged), and a per-call `--max-residual` on `extend add` and on `inbox`, where it joins pieces. The join Check reads the
   same value.
2. A piece that registers within the limit but above 0.5 px joins, and `add` warns `extend.strip_repainted` with the residual,
   the gain and the seam's mean difference, so the Owner knows the strip was re-rendered and looks at the seam.
3. True misses still fail: a strip from another scene, or one whose layout moved. Choose the ceiling from measurements and say
   why.
4. Check whether `add` takes a piece a pixel or two off the canvas size; if not, crop or pad it to the canvas with an info
   finding.
5. Spec and the Command's help describe the setting.

## Acceptance criteria

- [x] `[extend] max_residual` (default 0.5, more than 0 and at most 1.0, else `config.invalid`); `kiripix.toml` goes to
      `schema_version` 13 with a migration from 12 (the default is read, nothing is written).
- [x] `extend add --max-residual` and `inbox --max-residual` override it for one call; outside (0, 1.0] it is
      `extend.max_residual_invalid` with a `fix`. `op register-piece`'s `join.residual_high` reads the Project's value.
- [x] A join above 0.5 px under a raised limit warns `extend.strip_repainted`; a refusal within 1.0 px names
      `--max-residual 1` and the setting in its `owner_action`.
- [x] CLI seam: a synthetic re-rendered strip (sub-pixel wave + noise + per-channel gain, residual about 0.77) fails under the
      default and joins with the warning under `--max-residual 1`, under the setting, and through `inbox --file`; a piece from
      another scene fails under both; a limit over the ceiling is refused.
- [x] The real piece joins in a temporary Project (below).
- [x] `uv run mypy`, `uv run lint-imports` pass.

## Result

**The ceiling is 1.0 px** (`RESIDUAL_CEILING` in `kiripix/checks/join.py`), the same as `core/editof.py`'s limit for Look edits.
Measured with the registration `extend add` runs, on the real base (`ch01-003-laneway1.png`, 1678 x 937) and east piece:

| Piece | Residual | Patches kept |
|---|---|---|
| The real GPT Image piece | 0.665 | 238 of 250 |
| Another scene (`ch01-dungeon-r01`, `ch01-002-living-kitchen-morning`), whole or pasted into the strip | 1.343, 1.695 | 5, 4 |
| Another scene (`ch01-001-home-room-night`) | too few patches to fit | |
| The strip's lower half moved 2 px / 4 px against its upper half | 1.197 / 1.585 | 247, 241 |
| The strip's lower half moved 8 px / 16 px | 0.582 / 0.561 | 159 of 173 |

So 1.0 has room above the re-rendered piece (0.66) and stays below every miss that shows at the join. The 8–16 px case gets
through whatever the limit, because the outlier trim drops the moved half, but it is not a misregistration at the join: through
`extend add --max-residual 1` it joined with a seam difference of 3.5, the seam running through the strip columns that didn't
move. The tear is inside the piece, between its own halves, where no registration gate can see it. Under the old 0.5 limit an
untouched strip with that defect joined too, so this is not new.

**The off-size piece needs nothing.** `add` registers a scale per axis, so the 1679 px piece fits at scale 0.99958 x 1.00024
and lands on the 1678 px grid: the joined image is 2936 x 937 (1258 + 1678). No crop, pad or finding.

**The real join**, in a temporary Project with the room's base picked, `[extend] canvas = [1678, 937]`, `extend canvas --side
east --keep 420,234`: plain `add` is refused at 0.66 px with the new hint; `add --max-residual 1` joins at residual 0.665, gain
0.978 to 1.010, seam 1233 px with a difference of 3.3, and warns `extend.strip_repainted`. At 2x no seam shows. In the art repo
the Owner runs:

```
kiripix extend room.annex_laneway add "references/tests/Autumn Corner on Major Street.png" --side east --max-residual 1
```

or sets `max_residual = 1.0` under `[extend]` in its `kiripix.toml` for every GPT Image piece.

Code: `[extend] max_residual` in `ExtendSection` (`kiripix/core/settings.py`, schema 13, `_add_extend_max_residual`), the
`init` template; `residual_limit`, `repainted_findings` and the refusal hint in `kiripix/core/extend.py`; `max_residual` on
`ExtendInput` and `InboxInput`, passed through `core/inbox.py`; `check_join_residual` takes the limit, and `op register-piece`
reads the Project's. Nothing records the limit in the journal (it is a gate, not part of the join). No Stage changed, so no
`version` bump. Tests: four in `tests/cli/test_extend.py`; the tests that pin the Project's `schema_version` moved to 13.
