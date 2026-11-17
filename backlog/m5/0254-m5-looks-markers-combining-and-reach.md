---
status: todo
milestone: M5
type: spec
parent: 0236-m5-the-games-next-needs.md
---

# M5: Looks, the rest of open decision 8: their own Markers, two at once, and `reach`

Spec §6.1 (Looks), §9 (Looks), §16 (open decision 8), [ADR 0009](../../docs/adr/0009-a-rooms-looks-are-a-stage-on-the-room.md).
Part of [0236](0236-m5-the-games-next-needs.md), item 7. The game's `docs/MILESTONE_PLANS.md` M10-05 (R6: restoring the power
turns the lights on), and the M4 gate's laneway.

## What rooms now need

- **The laneway's back gate** (M4 gate): `back_gate_open` has its own `solid`, with the opening cleared. But `reach` reads
  the room without its Looks, so the yard behind the gate, (58, 345), 463 x 274, is reported as an unreachable island. The
  room is right, and the report is wrong.
- **R6, the game's M10:** power on lights the tunnel. That needs a Look that brings its own light Markers (and maybe
  emitters), and maybe two Looks at once (power on, and a gate open).

**The spec is stale on one point.** §6.1 says "A Look can't take collision away from the room yet". The code lets it: a
Look's `solid` starts as the room's, and `erase` clears it (`kiripix/recipes/looks.py`, `SOLID_DECISION`). Fix §6.1 and
decision 8 to say so, and that the game swaps the room's `solid` for the Look's while it shows.

## To decide (the Owner), then an ADR amending 0009

1. **A Look's own Markers:** lights, emitters and interactables placed for one Look. Proposed: a Marker may name a `look`.
   It's exported under the Look's nodes, `visible = false` (a light `enabled = false`), with the Look's metadata, and listed
   under the Look in `room.json`. `place` checks it as any Marker, against the Look's `solid` and walkable.
2. **Two Looks at once:** may the game show two? Proposed: yes, when their regions don't overlap; where they do, a
   `look.overlap` warning, and the game decides the order. Each Look's `solid` is a whole Mask, so two at once need a rule.
   Proposed: the game ANDs what each clears and ORs what each adds, against the room's, and Kiripix exports each Look's
   change (added and cleared) as well as its whole Mask. Or Looks that combine are declared, and each combination is checked.
3. **`reach` with a Look:** proposed: `reach` reports the room as now, and also per Look with its `solid` (and its own
   Markers). An island reachable under some Look is info, not a warning, naming the Look. The laneway's yard becomes info
   under `back_gate_open`.
4. **Walkable and navigation:** the exported `NavigationPolygon` is the room's. Proposed: one per Look that changes `solid`,
   hidden with it, so the game swaps navigation as it swaps collision.

A soft edge with binary alpha stays open (decision 8): no room needs one yet.

## Order

1. [0269](0269-m5-adr-looks-markers-combining-reach.md): the ADR draft by `reviewer`, then the Owner's review.
2. Once the Owner accepts the ADR, 0269 files the work tickets from it, each with its agent:
   - Markers per Look on `place` (core-engineer);
   - `reach` per Look (imaging-engineer);
   - export of the nodes, navigation and `room.json` (godot-export);
   - the UI (ui-engineer).

They aren't filed before the ADR, so they don't need rewriting if it changes the proposals.

## Acceptance criteria

- [ ] Spec §6.1 and §16 decision 8 corrected on taking collision away.
- [ ] The Owner's answers to 1–4, the ADR, and the work tickets filed.
