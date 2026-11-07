---
status: todo
milestone: M3
agent: core-engineer
type: ticket
---

# M3: find where a lift's time goes, and report all of it

Spec §10.2. Found by [0076](0076-m2-claude-layers-first-pass-trial.md). A lift's reported times don't explain how long it takes:

| Room, `run layers --rerun` | Wall time | Sum of Runner calls, about | `duration_s` reported |
|---|---|---|---|
| r02, 12 clicks | 35.5 s | 5 s | 0.83 s |
| r03, 47 clicks | 48.7 s | 10 s | 1.97 s |
| r01, 2 clicks | 29.9 s | 2 s | 0.39 s |
| r02, trims only, no Runner call | 4.9 s | 0 | 1.02 s |

- **About 23 s has no explanation.** In `history.jsonl` it falls between the last SAM 2 call and the first LaMa call, on each of the lifts
  checked (r02's first two and r01's). Loading a Runner is one guess, but it's untested: `_call` in `kiripix/core/graph.py` may not time the load.
- **`duration_s` looks like the Stage's work alone.** `kiripix/core/graph.py:577` starts its clock after the Runner calls have been made.
- **Why it matters:** the Owner finds lifting slow in the UI even with a warm Runner, and these cold lifts each waited about half a
  minute. [0083](0083-m3-ui-show-that-work-is-happening.md) shows the wait but doesn't shorten it.

## What to do

1. **Measure first.** Time a cold lift on r02 from the art Project by phase: Project and graph load, each Runner's load and unload, each
   embedding, decodes, fills, the Stage's own work and the write. Record the table here, and do the same for `Accept`, whose time
   nobody has measured, and for a warm lift in `serve`.
2. **Report it all.**
   - A result's `duration_s` for a Stage covers its Runner calls too, so that it adds up to what the Owner waited, less any wait for a lock.
   - A Runner call's history entry gains `load_s`, when it loaded the Runner. Its `duration_s` keeps meaning the call itself.
3. **Decide with the numbers.** If one phase is most of the wait and has a cheap fix, such as keeping one Runner loaded across a Stage's
   calls, make that fix here. Anything larger goes in a new ticket, named here.

## Not in this ticket

`run` returning `ok: false` with an `error` finding when it stops at `needs-review`. It looked wrong during the trial, but it's what the
contract says: spec §10.2 gives exit 3, "needs the owner", and `tests/cli/` holds that in place. An agent reads the exit code and the
`stage.needs_review` code. It stays as it is unless the Owner wants the contract changed.

## Acceptance criteria

- [ ] The phase table for a cold lift, a warm lift and `Accept` is recorded here, and the 23 s is accounted for.
- [ ] CLI seam: with a test Runner that takes a known time, a Stage's `duration_s` is at least that time.
- [ ] A history entry that loaded a Runner has `load_s`, and one that didn't, doesn't.
- [ ] A pinned rebuild makes no Runner call, so its `duration_s` stays the Stage's own work.
- [ ] Any fix made here stays within 8 GB of VRAM, and cancel still works during a load.
- [ ] `tests/cli/test_contract.py` passes.
