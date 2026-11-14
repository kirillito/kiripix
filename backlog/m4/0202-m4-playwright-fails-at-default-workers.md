---
status: todo
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

- [ ] `npm run test:e2e` passes three times in a row on Windows with the config's default workers.

Budget: 50–100k tokens.

## Notes

- 2026-11-13, after the M4 Looks and Loops batch (0187–0196): at default workers, 5 failed and 110 passed
  (`character.spec.ts:203`, and `loops.spec.ts:64`, `:135`, `:167` and `:215`), all timeouts. Rerun with `--workers=1`, all 7 tests in those two files
  passed, `loops.spec.ts:135` on its retry. The 0196 agent saw the same timeouts while other agents loaded the machine.
