---
status: todo
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0356-m6-npc-kind-and-choose-stage.md, 0357-m6-npc-checks.md]
---

# M6: UI: the NPC screen, a stacked preview the Owner dresses

Spec §11 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Over
[0356](0356-m6-npc-kind-and-choose-stage.md)'s `choose`; no logic in the UI beyond drawing.

## What to build

- **The NPC screen:** the base's idle in every direction, stacked and swapped as `preview --stage choose` draws it, at a
  whole-number zoom; beside it, the Wearables made on the base (toggle each, drag to reorder) and a picker per Part showing its
  named choices as swatches. Each change is one `set` of `choose`'s parameters (ADR 0015), and the preview reloads.
- **A crowd:** with [0359](0359-m6-npc-crowd.md) built, the status board's NPCs under one prefix as one strip, with "re-roll"
  on each.
- `npc.*` findings jump to the Wearable or Part they name.

## Acceptance criteria

- [ ] Playwright against a real `kiripix serve`: toggling a Wearable and picking a colour each `set` one parameter and redraw.
- [ ] `npm run build` passes.
- [ ] An eye check by the Owner on three NPCs, noted here.

## Result

Built over `choose` and the `npc` Commands; no Python changed, no backend gap found. `status` stays `todo`: only the Owner's eye check
(the third criterion) is open.

- **The NPC screen** (`web/src/npcScreen.tsx`, `NpcScreen`, in the main area of an NPC's `choose`): the figure is `preview --stage
  choose` (called again on each refresh) shown as an `<img>` at its natural size with `image-rendering: pixelated`, at zoom 1 to 4
  (buttons, or `Z` to cycle; default 2), so the page never scales it. Beside it: every Wearable made on the NPC's base (from
  `useWearables`), each a checkbox, with an up and a down button and drag-to-reorder for the worn ones (top of the stack first); and a
  swatch picker per ramp-table row that has named `choices` (from `describe project`), with "none" to leave a Part unset.
- **One change, one `set`:** a toggle writes `wearables`, a drag or arrow writes `wearables`, a swatch writes `colours`; each is one `set`
  of one parameter, then `choose` is run again in the same action (no Runner), the same as a Mask edit's rebuild (ADR 0006), so the figure
  shows it. A drag gives only the moved Wearable an `id@N` of its own, strictly between its new neighbours; where the orders leave no
  room it numbers the stack again in tens. That integer is the only arithmetic the screen does. The generic panel no longer shows the
  `wearables` and `colours` text fields on this Stage, so there is one way to change each.
- **Findings:** an `npc.*` finding's jump (`data.wearable`/`data.part`, else `field` `wearables/<id>`/`colours/<part>`) focuses the
  Wearable's row or the Part's swatches (outline and scroll into view). The Checks list in the panel is the existing one.
- **The crowd:** `NpcCrowds` on the status board groups NPC IDs `npc.<prefix>_<digits>` by prefix (nothing is stored), draws each
  group's strip with `cast-sheet --match 'npc.<prefix>_*'` (scale 2, direction `s`), and lists each NPC with "re-roll": `new npc <id>
  --reroll`, then `run <id> choose` (a re-roll writes the choice only, and the figure needs `choose` built). A `new.crowd_unsatisfied`
  warning shows beside the NPC.
- **Edits to shared files, small:** `web/src/App.tsx` (the import, `npcFocus`, `setChoice`, `rerollNpc`, `isNpcChoose`, one branch in
  `main`, the `crowds` prop, the param filter, one line in `jump`) and `web/src/components.tsx` (a `crowds` slot on `StatusBoard`);
  styles at the end of `web/src/styles.css`.
- **Test:** `web/e2e/npc.spec.ts`, one character chain on the fake Blender (a base, two Wearables, a ramp table with choices, an NPC and
  a crowd of two): the board's strip and a re-roll that changes the NPC's parameters; the figure at zoom 2 with whole-pixel size and
  `pixelated`; `Z` and the zoom buttons; toggling the cap, picking `hair=blond` and `top=red`, and a drag, each seen as exactly one
  `/api/set` with one assignment; the arrows; and a choice renamed in `kiripix.toml` giving `npc.colour_choice`, whose jump focuses the
  Part.
- **Eye check (open):** the Owner looks at three NPCs and notes it here. Screenshots of a run: `web/shots/0360-npc-screen.png`,
  `0360-npc-crowd.png`, `0360-npc-finding.png` (the fake Blender's flat frames; the eye check needs real NPCs).

