---
status: done
milestone: M3
agent: ui-engineer
type: ticket
---

# M3: findings on screen that a person reads, not skims past

Spec §11. Found by the Owner at the [M2 gate](m2/0058-m2-gate.md): the "Last Command" list (`web/src/App.tsx`, the `notice` FindingList) is
"hard to read for a human, to tell that something is happening or something needs to be done. It looks noisy, like build warnings in
Visual Studio; I tend to just ignore them."

Today the screen has three lists: the Stage's Checks, Last Command and the Asset's problems, each showing every finding with its
code, message and `fix` or `owner_action` as the CLI gives them. The Owner can't tell which one asks for something.

## What to build

- **One line that says what to do next,** when anything needs the Owner: the `owner_action` of the most pressing finding, as a
  button where the UI can do it (Accept, Re-run, pick).
- **Errors above warnings above info,** with the info findings collapsed to a count by default, such as `export.pending`.
- **The same finding once,** whichever list it came from.
- **Plain words first:** the message leads; the dotted code and the CLI command are there for an agent, behind a toggle or in a
  smaller line.
- **Nothing that only repeats the status,** like a `stage.needs_review` error under a Stage already shown as `needs-review`.

## Acceptance criteria

- [x] Playwright: a room with a `needs-review` Stage shows one "next" line with a working button, and no duplicate error for it.
- [x] Info findings are collapsed to a count, and expand on a click.
- [x] A finding that appears in two lists today shows once.

## Findings (ui-engineer)

- Built in `web/src/components.tsx` (`readable`, `pressing`, `FindingList`) and `web/src/App.tsx`: the message leads, the dotted code and `fix`
  are one small line below it; errors sort above warnings above info; info is a "Show N notes" count; a finding in Last Command that
  Checks or the Asset's problems already show is dropped; `stage.needs_review` / `stage.needs_input` are dropped when the Stage's status
  already says it. One "next" line (`next-hint`) at the top of the panel, with an Accept or Re-run button where the UI can do it.
- Info collapse is proved by `findings.spec.ts` with a real `export.pending` (a prop built to done, with `[export.godot]` pointing at a temporary
  Godot project; the Run's answer is asserted to contain it). The duplicate is proved with `cutout.chroma_keyed_nothing`, which the Run and the
  Checks both return: the test asserts the Run's answer holds it and that it shows exactly once. It also shows the Run's other finding
  (`palette.mapping_error`) and drops the `stage.needs_input` of the waiting footprint Stage.
- A click during a Run's landing WAS dropped: it was a 0083 bug, not a test race. The prop/place/mask/layer tools ignored gestures while `busy`
  (a Run's job id was set), so a click made then vanished silently. Fixed: the tools no longer check `disabled`; `perform` queues each gesture
  behind the Run, as 0083 promises. The wait I had added in `prop.spec.ts` is removed, and the test passes without it.
- `masks.open_edge` is an info finding, so it now sits behind the count; `masks.spec.ts` expands it first.
- The `next` Command's owner_action for a prop footprint reads "Draw it again: kiripix decide ..." (a CLI line, not plain words): a
  backend wording question for the owner.
