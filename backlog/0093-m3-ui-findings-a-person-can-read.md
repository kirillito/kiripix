---
status: todo
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

- [ ] Playwright: a room with a `needs-review` Stage shows one "next" line with a working button, and no duplicate error for it.
- [ ] Info findings are collapsed to a count, and expand on a click.
- [ ] A finding that appears in two lists today shows once.
