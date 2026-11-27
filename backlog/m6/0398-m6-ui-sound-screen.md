---
status: done
milestone: M6
agent: ui-engineer
type: ticket
parent: 0393-m6-sound-kind.md
---

# M6: UI: listen to the Takes and pick

## What to build

- A sound Asset's screen: the waveform with its Takes, click a Take to play it (source and processed), A/B the two,
  tick Takes into the pick, drag to reorder variations; the slice and process parameters with a re-run.
- Play a picked set in sequence at a set interval (footsteps at walking pace), to hear them as the game will.
- The review queue (0325) lists a sound Asset whose pick or process is waiting for the Owner.

## Acceptance criteria

- [x] The Owner picks four steps and approves the export without the CLI.

## Result

`web/src/soundScreen.tsx` (new), `web/src/soundAudio.ts` (new), wired in `App.tsx`; `web/e2e/sound.spec.ts` is the flow. The Takes' choosing
Decision is `keep`, in the interface text too.

- One screen per Stage of a Sound (`source`, `slice`, `keep`, `process`, `export`). `source`: recordings with Play and Pick, and an import
  with Provenance (author, licence, URL). `slice`/`keep`/`process`: `sound-sheet`'s picture with a button over each Take's box and row (the
  waveform), the Takes' table from `sound-takes`, a click plays the Take from the whole recording (Web Audio, so float WAV works). `keep`:
  tick Takes in, a Variation list to drag or arrow into order, each change one `decide keep` (the whole list, by spans). `process`:
  Variations from `process.json`, Play processed / Play source / A/B, and a per-Take `tune` form built from `describe`'s `tune` schema, one
  `decide tune`. `export`: the encoded files, Play, then "Export to the game" asks with a dry run and an Approve button (`export`).
- The kept set plays in sequence at an adjustable interval (default 450 ms, start to start), source or processed. Keys: 1-9 play Take N,
  X swaps A/B, K keeps or drops the selected Take, S plays the kept set, Space plays or stops, Esc stops. Ctrl+Z/Ctrl+Shift+Z are
  `undo`/`redo`. Parameters (slice, process) and Run/Accept are the Stage panel's, from `describe`.
- The queue lists a Sound whose `keep` is `needs-review` (a moved Take). A `keep` in `needs-input` is not a queue stop, because the Stage's
  `needs_input` carries a `command` (`sound-takes`), which `core/queue.py` counts as an agent's step. That is the backend's rule; to show it in
  the queue it would need an `owner_action` on that `needs_input`.
