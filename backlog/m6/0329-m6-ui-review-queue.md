---
status: done
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0325-m6-review-queue-command.md, 0326-m6-hand-over-note.md]
---

# M6: UI: the review queue, one keyboard flow over every stop

Spec §11 and §14 (M6, a review queue). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Built on
[0325](0325-m6-review-queue-command.md)'s `queue`; the UI holds no logic of its own.

## The gap

To approve a district's first passes, the Owner opens each room, finds its Stage in the stage bar, and reviews. The status
board's "needs me" filter lists Assets, not stops, and has no next.

## What to build

- **Queue mode**, reached from the top bar ("Queue · 23") and from the status board. It walks `queue`'s items in order. Each
  item opens its Asset on its Stage's own screen, as clicking the Stage does today, with a strip above the canvas: "7 of 23",
  the item's type and reason, and the Stage's live hand-over notes.
- **A `review` item** opens with the screen's before/after of the replayed result, and Accept is the primary action (§11).
  **An `input` item** shows its `owner_action`. **A `finding` item** jumps to its position on the canvas, as a finding click does.
- **Keys:** `A` accepts (a `review` item), `→` or `N` the next item, `←` or `P` the previous, `Esc` leaves queue mode. The
  Stage's own keys work as usual, so the Owner fixes in place; after a Decision or an `accept`, the queue refreshes and moves
  on to the next item still waiting.
- An `--match` field narrows the queue to a district (the 0327 glob), kept for the session.
- `agent_fixable` shows as one line ("4 findings an agent can fix") with the commands to copy, never as items.
- The queue refreshes when the Project changes (an agent working behind the Owner), keeping the current item if it's still
  waiting.
- Active time is tracked as on any Stage screen, so `stats` measures the queue sitting.

## Acceptance criteria

- [x] Playwright against a real `kiripix serve`: a Project with two `needs-review` Stages on two rooms and one owner-action
      finding; the Owner steps through all three by keyboard, accepts both reviews with `A`, and the queue ends empty.
- [x] Playwright: a note written by `kiripix note` shows on its item.
- [x] `npm run build` passes (the type check).

## Result

Queue mode is built on `queue` alone; the UI holds no logic. `web/src/queueMode.tsx` holds the strip, the "Queue · N" button
and the item identity; `App.tsx` fetches `queue` with every refresh (so a Project change, an agent's note or a Decision
refreshes it), keeps the current item while it still waits, else moves to the item now at its place, and opens each item as a
Stage click does (a finding also jumps to its position). Keys: `A` accepts a review, `→`/`N` next, `←`/`P` previous, `Esc`
leaves. The match field is kept for the session (sessionStorage) and `?queue=<glob>` opens queue mode on a glob, for 0330's
"Review this district" (`openQueue(glob)` in App). `agent_fixable` is one line with the commands to copy. Active time is the
Stage screen's own `track`. No Stage `version` bump.

Notes: in queue mode the queue keys win over a Stage's use of the same key (arrow panning, `N`/`P` on the frame screens, a Mask
whose key is `a`); `Home` and Space-drag still move the view. Tests: `web/e2e/queue.spec.ts` (screenshot `web/shots/queue-mode.png`).
