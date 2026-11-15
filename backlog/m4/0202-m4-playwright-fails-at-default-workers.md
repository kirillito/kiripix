---
status: done
milestone: M4
agent: qa-engineer
type: ticket
---

# M4: the Playwright suite fails under its default worker count

Found on 2026-11-12. `npm run test:e2e` on the owner's Windows machine: 20 failed, 82 passed. The failures spread across 12
spec files, most untouched by the change under test (area, character, findings, layers, legible, masks, navigation, place,
prop, work, ysort). Rerun with `--workers=2`, all 76 tests in those files passed. Each test starts its own `kiripix serve`
(`web/e2e/harness.ts`), and `web/playwright.config.ts` sets `fullyParallel: true` with no `workers`, so Playwright takes half
the cores.

## What to find and fix

- Read a few of the failures' traces (`test-results/*/trace.zip`) and say what fails under load: a server that starts too
  slowly, a timeout too tight for a Stage run, or a test that depends on timing.
- Fix the cause where it is a test's race or wait. Where it is only load, cap `workers` in the config (on Windows and CI
  both, or per platform) and say why in a comment.
- 0139 raised one test's timeout to 120 s to get through; check whether that is still needed afterwards.

## Acceptance criteria

- [x] `npm run test:e2e` passes three times in a row on Windows with the config's default workers.

Budget: 50–100k tokens.

## Notes

- 2026-11-13, after the M4 Looks and Loops batch (0187–0196): at default workers, 5 failed and 110 passed
  (`character.spec.ts:203`, and `loops.spec.ts:64`, `:135`, `:167` and `:215`), all timeouts. Rerun with `--workers=1`, all 7 tests in those two files
  passed, `loops.spec.ts:135` on its retry. The 0196 agent saw the same timeouts while other agents loaded the machine.

## Result (2026-11-14)

- **What failed.** First run on a quiet machine: 6 failures, all of `loops.spec.ts`, and they also failed at `--workers=1`. That was a
  product bug, not load: 0219 gave the `loops` Stage a `pick` Decision, and `web/src/App.tsx` took any Stage with a `pick` for the
  Source screen (the Variant grid), so the canvas never appeared. The Owner approved the one-line fix (`isSource` also excludes
  `LOOPS_STAGE`), which the main session applied. After it, `loops.spec.ts` and the new `loopedits.spec.ts` pass without edits (the
  `lift` and `loop.held` changes needed no test change).
- **Under load.** With the fix, each default-workers run (half the cores, about 8 min) still lost one or two tests at random, each a
  different one. Cause: every test starts a server and builds its room with several `uv run` calls, 20 to 25 s alone; shared, the
  slowest take 50 to 60 s against a 60 s limit (`character.spec.ts:203`, `loops.spec.ts:135`, `frames.spec.ts:193` at 58 to 60 s), and
  a few steps raced the screen.
- **Changed (tests and config only).**
  - `web/playwright.config.ts`: `timeout` 60 s to 120 s, with a comment. A stuck test still fails on its own 20 s `expect`. No
    `workers` cap: the suite runs 8 min at the default and a cap would only lengthen that.
  - `web/e2e/loops.spec.ts`: the eyedropper clicks in `floorCycle` retry until the colour is in the cycle (the eyedropper ignores a
    click before the rebuilt room has loaded); the wait for `loop.flash` is 60 s (the flicker Stage rebuild is slow when shared).
  - `web/e2e/frames.spec.ts`: the canvas pixel check polls, because the frame's image decodes after `data-frame` is set.
  - `web/e2e/shell.spec.ts`: Run is pressed again until `fit` is done, because the first click right after the Pick was sometimes lost.
- **Results at the config's default workers** (after `npm run build`): the final three runs in a row, 118 passed each (8.0, 8.0 and
  8.4 min). The runs before the last two edits had 1 or 2 random failures each.
- **0139's 120 s timeouts** (`area.spec.ts:49` and `:112`; also `frames`, `sprite` and `emitter` set their own) are now the default,
  so they are redundant but harmless; left in place. The tests near the limit are slow because of setup, not a bug.
