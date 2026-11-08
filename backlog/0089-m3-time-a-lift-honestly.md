---
status: done
milestone: M3
agent: core-engineer
type: ticket
---

# M3: find where a lift's time goes, and report all of it

Spec §10.2. Found by [0076](m2/0076-m2-claude-layers-first-pass-trial.md). A lift's reported times don't explain how long it takes:

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

- [x] The phase table for a cold lift, a warm lift and `Accept` is recorded here, and the 23 s is accounted for.
- [x] CLI seam: with a test Runner that takes a known time, a Stage's `duration_s` is at least that time.
- [x] A history entry that loaded a Runner has `load_s`, and one that didn't, doesn't.
- [x] A pinned rebuild makes no Runner call, so its `duration_s` stays the Stage's own work.
- [x] Any fix made here stays within 8 GB of VRAM, and cancel still works during a load. (No fix was made to the load itself; see 0118.)
- [x] `tests/cli/test_contract.py` passes.

## Findings (measured on a copy of the art Project; Windows, RTX 2070 Super, `onnxruntime` 1.31.1)

**The 23 s is LaMa's load.** `onnxruntime.InferenceSession(lama_fp32.onnx)` takes 19 to 21 s, every time, on the CUDA provider and on the
CPU one alike (22 to 32 s); it is one core at 100% for the whole time, so it's CPU work inside ORT, not a copy to the GPU. `_call` didn't
time it, because the load happens before the first call's clock starts. [0118](0118-m3-lama-load-takes-20-seconds.md) holds the follow-up:
none of the cheap session options shortened it (listed there), so no fix was made here.

**Cold lift, r02** (`run layers --rerun` after deleting `pinned/`; 31.9 s wall, `duration_s` reported 0.89 s):

| Phase | Seconds |
|---|---|
| Process start, imports, Project and Asset load, first state | 0.9 |
| SAM 2: load | 1.6 |
| SAM 2: first call (the embedding) | 0.5 |
| SAM 2: the other 15 calls (decodes) | 0.4 |
| SAM 2: unload | 0.05 |
| Working out the calls again after SAM 2's pins (hashing) | 0.5 |
| **LaMa: load** | **20.5** |
| LaMa: first call, then 12 more | 0.9, then 0.2 each (3.3 in all) |
| LaMa: unload | 0.14 |
| Working out the calls again after LaMa's pins | 0.5 |
| The Stage's own work (what `duration_s` reported), its write | 0.9 |

**Warm lift in `serve`** (the same lift through `run_asset(keep_warm=True)` twice in one process; 27.5 s, then 26.6 s). Only SAM 2 is
warm, and `one_runner_loaded` unloads it when LaMa loads, so the second lift loads SAM 2 again (0.9 s) and LaMa again (19.6 s). The Owner's
"slow even with a warm Runner" is this: LaMa isn't kept warm, so every lift in the UI pays 20 s. Also in 0118.

**`Accept`** (the code it runs, timed in a fresh process against the copy; it's Owner-only, so it wasn't run through the CLI, and the copy was
not in `needs-review`, so the appends weren't timed): Project and graph load 0.04 s, state of the Stage 0.05 s, unreviewed pins 0.02 s,
replay on other images under 0.01 s, the states of all Stages 0.05 s, imports 0.7 s. It makes no Runner call and hashes nothing new.
It doesn't wait on anything; the wait the Owner sees on accept is process start and the status afterwards.

## What changed

- A Stage's `duration_s` (result and `history.jsonl`) now includes its Runner calls: pulling, loading, the calls, unloading, less any wait for the
  GPU lock. A `needs-review`, `failed` or `skipped` result after calls carries it too.
- A Runner call's history entry has `load_s` when its call loaded the Runner (the cold path and the warm one); `duration_s` there is still the
  call alone.
- The test Runners take a known time from `runner-load-seconds` and `runner-call-seconds` in the Project folder.
