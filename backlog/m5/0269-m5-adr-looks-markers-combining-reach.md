---
status: done
milestone: M5
agent: reviewer
type: ticket
parent: 0254-m5-looks-markers-combining-and-reach.md
---

# M5: ADR draft: a Look's Markers, two Looks at once, and `reach` per Look

Part of [0254](0254-m5-looks-markers-combining-and-reach.md). The spec ticket's four proposals become one ADR amending
[ADR 0009](../../docs/adr/0009-a-rooms-looks-are-a-stage-on-the-room.md), for the Owner to accept or change. The work
tickets are written from the accepted ADR, not before it.

## What to do

- Draft `docs/adr/0013-...` (the next number): the context (the laneway's yard behind its gate, the game's M10 R6), the four
  decisions as 0254 proposes them, and their consequences:
  - `place.json`'s, `reach.json`'s and `room.json`'s formats and `schema_version` bumps;
  - the Manifest's ID lists;
  - what the game has to do (swap collision and navigation, enable a Look's lights);
  - what stays open (soft edges).
- Fix spec §6.1 and §16 decision 8 where they say a Look can't take collision away (the code lets a Look's `solid` erase).
- Once the Owner has accepted the ADR, write the work tickets 0254's "Order" lists, each with its agent, acceptance criteria
  at the CLI seam, and `depends_on`. Writing them is this ticket's last step (the reviewer splits specs into tickets).

## Acceptance criteria

- [x] The ADR drafted as `proposed`, with the spec's stale sentences fixed.
- [x] The Owner's acceptance recorded in the ADR (the Owner's, not the agent's).
- [x] The work tickets filed from the accepted ADR, and listed in 0254 and 0236.

## Result (2026-11-17)

Drafted [ADR 0013](../../docs/adr/0013-a-look-has-its-own-markers-collision-and-reach.md), `proposed`. Spec fixed: §6.1's
Looks `solid` Decision and the `looks` row's Owner input (a Look's `erase` takes collision away), §16 decision 8 (that part
settled, the rest pointing at ADR 0013), and §9's Room row, which told the game to enable a Look's polygons while leaving the
room's `solid` body on, so an `erase` never took effect in the game.

For the Owner, before accepting:
- **Two Looks at once:** the "AND what each clears, OR what each adds" rule works on the Mask PNGs but not on
  `CollisionPolygon2D`s, so the draft has export split the bodies (the room's minus every cleared pixel, plus a cleared body
  per set of Looks). Navigation and `reach` can't be split that way: two `solid`-changing Looks shown together get neither.
  Declared combinations are under "We considered" if that matters.
- **The Manifest:** `ids.look_markers` is added without a `schema_version` bump, as `looks`, `loops` and `states` were.
  CLAUDE.md's rule would bump it with a migration; the Owner's call.
- This ticket's file names were wrong: `place` writes `markers.json` (not `place.json`), and `reach` writes `report.json`
  (not `reach.json`), which has no `schema_version` yet. The ADR uses the real names.

Left: the Owner's acceptance, then the work tickets.

### Accepted (2026-11-18, main session)

- **The Owner accepted ADR 0013** with one change: `ids.look_markers` bumps the Manifest to schema 3, with a pure
  `migrate_v2` beside `migrate_v1` (an older Kiripix refuses it; each Manifest is rewritten once at its next export). The
  ADR records it. Two Looks that both change `solid` stay as drafted (split collision bodies; no navigation or `reach` for
  the pair).
- The ADR's versions corrected: `reach` was already at 2 (0266), so it goes to 3, and `export` to 3.
- **Work tickets filed:** [0314](0314-m5-look-markers-on-place.md) Markers, walkable and clear per Look on `place`, and
  `look.overlap` (core-engineer); [0315](0315-m5-reach-per-look.md) `reach` per Look (imaging-engineer, after 0314);
  [0316](0316-m5-export-look-markers-collision-navigation.md) export, `room.json` 12 and the Manifest 3 (godot-export,
  after 0314 and 0315); [0317](0317-m5-ui-look-markers-and-reach.md) the UI (ui-engineer, after all three).
