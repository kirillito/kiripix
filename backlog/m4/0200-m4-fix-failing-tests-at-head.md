---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0133-m4-rooms-for-grid-battles.md
---

# M4: four tests that fail at 94bc5fa

Found by the full suite run after 0135, 0138 and 0139 (2026-11-12). None of the four touches a file those tickets changed;
they came in with earlier commits (0137, 0167).

## What to fix

- `tests/cli/test_serve.py::test_every_command_has_a_rest_body`: `BODIES` has no entry for `ramps-add` (0167). Add one.
- `tests/cli/test_reachability.py::test_describe_says_reach_is_implemented_with_its_checks`: the reach Stage now lists
  `area.not_reached` (0137), which the test doesn't expect. Add it.
- `tests/cli/test_reach_probe.py::test_on_a_done_room_the_answer_is_the_reach_report` and
  `::test_a_pending_box_that_opens_a_way_shows_the_marker_reached_while_masks_awaits_review`: `room.json`'s reach report has
  `areas` (`kiripix/recipes/room.py`, `_reach_report`), and the Probe's answer (`kiripix/core/reach_probe.py`) doesn't, so
  "the answer is the reach report" no longer holds. 0137's Notes say "The Probe `reach` doesn't report areas", which
  contradicts the Probe's promise. Recommended: the Probe reports areas too, so its answer is the Stage's report; ask the
  Owner if you think the exception should stay, and then change the tests' claim instead.

## Acceptance criteria

- [ ] The four tests pass, and the full suite has no other failure.

Budget: 20–50k tokens.
