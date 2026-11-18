---
status: done
milestone: M5
agent: ui-engineer
type: ticket
parent: 0257-m5-prop-states.md
depends_on: [0259-m5-prop-stages-per-state.md]
---

# M5: UI: a Prop's states

Spec §11. Part of [0257](0257-m5-prop-states.md). Built on the Commands of [0258](0258-m5-prop-state-decision-and-import.md)
and [0259](0259-m5-prop-stages-per-state.md), with no logic of the UI's own.

## What to build

- **A state strip** on the Prop's screens: the default and each state as a thumbnail, with its pick, status and findings.
  Declare, import and pick a state from it.
- The `cutout`, `fit` and `footprint` screens work on the selected state, and every Decision they record names it.
- **Side by side:** the states at 1x on one ground line, each at its origin, so the Owner sees that they match in scale.

## Acceptance criteria

- [x] Playwright: on a fixture Prop with two states, selecting the second and drawing a footprint records a Decision naming
      it, and the side-by-side view shows both at their origins.
- [x] `npm run build` passes.

## Result

- **State strip** (`web/src/propScreens.tsx`, `StateStrip`, in the Stage panel of every Prop screen): the default and each declared
  state as a thumbnail at a whole-number scale (the furthest built Stage's image, else the picked Source), its pick, its size
  and its findings (by file path or "the state <id>"). Selecting one is a view choice. Declare: one `decide` of a `state`
  Decision on `source`. Import: `import --state` (the strip's button, or the Variant grid of `source` while a state is
  selected). Pick: `pick --state` (the grid, digit keys).
- `footprint` records its Decision with `state` while a state is selected, and shows only that state's Decisions; `fit` has a
  `state_offset` form (one `decide`) for the crop of the selected state. `cutout`, `fit`, `palette` and `finish` show the
  selected state's images. Those Stages have no other Decision of their own, so no other Decision needs the name.
- **Side by side** (`SideBySide`): every state at one scale (1x, raised in whole numbers) on one ground line, each at its
  footprint origin (a state with none stands on its bottom edge and says so).
- Gaps for the backend, none blocking: `show` lists no state output files, so the UI names them from the default's path
  (`<stage>/states/<id>/<file>`, ticket 0259's layout); and a Stage has one status for all its states, so the strip shows a
  state's pick and findings but no status of its own. No remove or rename of a state in the UI yet (`state_remove`, `state_rename`).
- Tests: `web/e2e/prop-states.spec.ts` (3 flows) pass; `prop.spec.ts` passes (one run flaked on `lock.busy` from the
  active-time `track` call racing an `import`, passes alone). `npm run build` passes.
- Screenshots: `web/shots/prop-states-footprint.png`, `web/shots/prop-states-side-by-side.png`.

## After review (2026-11-17)

The UI no longer guesses: `show` lists each state's built images (`states[].images`: per Stage, `image` and `input_image`), and
a finding about a state carries it as `position.state` (left out of the JSON for the default). `about_state` in
`recipes/prop_states.py` sets it. Tests: `test_prop_state_stages.py` (`show` lists the images; the finding names its state)
and the contract sample.
