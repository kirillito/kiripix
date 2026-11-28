---
status: todo
milestone: M7
agent: ui-engineer
type: ticket
depends_on: [../m7/0335-m7-ui-style-scores.md]
---

# M7: UI: the Owner finds the style panel and "Make this a style reference" on any Asset

Follow-up to [0335](../m7/0335-m7-ui-style-scores.md). The Owner, 2026-11-27: in the art Project, they can't find where to make
an Asset a style reference, on any Asset they opened.

## The gap

`StylePanel` (`web/src/styleScreen.tsx`) holds the only "Make this a style reference" and "Remove reference" buttons. `App.tsx`
mounts it in the Stage panel only when `styleShown` holds: `probe style` has answered for the open Asset, and the selected Stage
is the one the Probe names (`palette` for a room, `finish` for a sprite or character, `export` for a prop). On every other
Stage, and before `probe style` answers, nothing shows that style references exist at all. In the art Project
`[style] references = []`, and the Stage the Probe names is often not built in a given checkout (`work/` is not in git), so the
panel says "nothing to measure", if it shows at all.

## What to build

- **Reproduce first** on a copy of the art Project: open `room.annex_bedroom`, `sprite.raccoon` and a character, each on every
  Stage, and record where the panel shows and where it doesn't. If it doesn't show on the Probe's own Stage either, that is a
  bug: find it and fix it before the rest.
- **Reference from anywhere:** "Make this a style reference" / "Remove reference" for the open Asset on every Stage of a Kind
  the Probe supports, for example in the Asset's header, without the measure bars. The bars stay on the Probe's Stage.
- **Say where the bars are:** on any other Stage, a line such as "Style: measured on `palette`" that opens that Stage.
- **Not built:** when the Probe's Stage isn't built, the panel says which Stage to run, with its Command, instead of only
  "nothing to measure".
- The status board's reference star (0335) stays as it is.

## Acceptance criteria

- [ ] Playwright against a real `kiripix serve`: on a test room's first Stage, making it a reference works, and the board shows
      the star; a link from that Stage opens the measured Stage with the bars.
- [ ] `npm run build` passes.
- [ ] The Owner makes a room, a sprite and a character references in the art Project without being told where to look, and
      then does 0335's eye check (one character, one sprite, one room), noted in 0335.
