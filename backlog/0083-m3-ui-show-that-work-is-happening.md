---
status: todo
milestone: M3
agent: ui-engineer
type: ticket
---

# M3: show that a click did something and Kiripix is working on it

Spec §11. Found by the Owner in [0076](m2/0076-m2-claude-layers-first-pass-trial.md). On all three rooms, `Accept` took a long time with
no sign of working: "you click and nothing happens, and you're not sure if it's working or not". The same goes for lifting a Layer
and drawing a Mask. There's almost no way to tell, and it causes extra clicks.

## What's there today

All in `web/src/App.tsx`, unless named.

- **`Accept`** goes through `perform` with no job (line 309), so `busy` stays false. The button stays live and shows no change until
  the result lands.
- **`run` and the rerun** set a job, so the primary button becomes Cancel and parts of the screen are disabled. Nothing says what's
  running, or for how long.
- **A lift or a Mask edit** (`rebuilt`, line 243) sets `rebuilding` and deliberately doesn't make the screen busy, so quick strokes
  queue in order and none is dropped. So a repeat click is kept: on the layer screen each one becomes a Decision.
- **The progress line** (`data-testid="progress"`, line 534) shows the last `progress` event from `api/events`. It's a small hint, and
  it's empty until an event arrives and between events.
- **How long this takes:** a lift took 30 to 49 s of wall time in 0076, about 23 s of it between the last SAM 2 call and the first
  LaMa call, with nothing to see. `Accept`'s time was never measured, because `history.jsonl` doesn't record it.

## What to build

Web only. The UI knows when each action starts and ends, so nothing here should need a new Command or event.

- **An answer to every action, at once:** within a frame of the click, whether or not the server has replied. This covers opening
  the room list and opening a room (13 to 15 s each at the [M2 gate](m2/0058-m2-gate.md), with nothing on screen; the cause is
  [0090](0090-m3-status-without-re-deriving-lifts.md)), `Accept`, `run` and the rerun, the `palette` Stage's run, layer clicks and trims, Mask brush, flood, click and border, undo and redo, imports and pick.
- **On the canvas, where the Owner is looking:**
  - A layer or Mask click leaves a mark on its pixel until its result lands.
  - A brush stroke stays drawn, marked as pending, until the Stage has rebuilt.
- **One status strip, always in the same place:**
  - What's running, in the glossary's words (`Accepting layers`, `Lifting into bench`), with the time elapsed.
  - An animation that moves as long as the work is running, so a long Runner call doesn't look like a hang.
  - The latest progress message, when there is one.
  - A bar with a real fraction only where the events give one. Otherwise no invented percentage.
  - The number of actions still queued (`3 waiting`).
- **`Accept` while it runs:** the button shows that it's working and can't be pressed twice.
- **Queued clicks stay queued:** none is dropped or merged, as today. The change is that the Owner sees them waiting.
- **When it ends:** a failure clears the marks and the strip and shows the finding as now, and a cancel clears them without an error.
  If the event stream is lost, the strip still shows the action and its elapsed time.

**Not in this ticket:** making `Accept` or a lift faster. Once the strip shows elapsed time, the Owner can see which waits are worth
a ticket of their own, starting with the 23 s gap. `Accept` doesn't gain a Cancel here either.

## Acceptance criteria

Playwright, with the response held back by `page.route` so the wait can be seen:

- [ ] Opening the room list and opening a room show the strip at once, before the response.
- [ ] `Accept`: the strip and the button's working state show before the response, and a second press sends no second request.
- [ ] A layer click leaves a mark on its pixel before the response, and the mark goes when the result lands.
- [ ] A brush stroke stays visible, marked as pending, until the Stage has rebuilt.
- [ ] Three quick layer clicks all reach the journal in order, and the strip shows the waiting count falling.
- [ ] `run` and the rerun show the strip, with elapsed time rising, and Cancel still works and clears it.
- [ ] With no progress event at all, the strip still names the action and its animation runs.
- [ ] A failed action clears the marks and the strip, and shows its finding.
