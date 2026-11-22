---
status: todo
milestone: M6
agent: ui-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0334-m6-style-references-and-wiring.md]
---

# M6: UI: an Asset's style beside its references

Spec §11 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Reads
[0334](0334-m6-style-references-and-wiring.md)'s `probe style`; no logic in the UI.

## What to build

- **A style panel** on the screen of the Stage that the style Checks measure: each measure as a small bar showing the
  references' range and the Asset's mark in it, out-of-range ones marked. Clicking a `style.*` finding opens it.
- **The references side by side:** the Asset's image beside the closest and furthest reference's, at the same whole-number
  zoom, so the Owner judges by eye what the numbers say.
- **Picking references** (Owner only): "Make this a style reference" and "Remove reference" on any supported Asset, calling
  `style-add` and `style-remove` with the session token. The status board marks reference Assets.

## Acceptance criteria

- [x] Playwright against a real `kiripix serve`: making two test Assets references shows a third's bars, with an
      out-of-range measure marked and its finding shown.
- [x] `npm run build` passes.
- [ ] An eye check by the Owner on one character, one sprite and one room, noted here.

## Result (2026-11-20, ui-engineer)

Built on `probe style`, `style-add` and `style-remove` only; the Python side is untouched.

- `web/src/styleScreen.tsx` (new): `StylePanel`, on the screen of the Stage the Probe names (`probe.stage`: `finish` for figures, `palette` for a room, `export` for a prop). A bar per measure the Asset has (outline density for the figures, pixel scale for every Kind): the references' range as a band, the Asset's mark, the Check's limit as a dashed tick, and "out of range" when a `style.*` finding names the measure (the Probe's findings, not a comparison made here). The Probe's own `style.*` messages are shown under the bars. Below them the Asset and every built reference side by side at one integer zoom (starts where the largest picture is about 120 px; `-` and `+` change it), nearest-neighbour, the Probe's `furthest` named. "Make this a style reference" / "Remove reference" call `style-add` / `style-remove` through the usual `perform` (the session token goes with `call`).
- `web/src/App.tsx`: `refresh` also asks `probe style` (for the open Asset, else the first one, since the references are the Project's); `styleShown` mounts the panel; a click on a `style.*` finding in Checks scrolls the panel into view and outlines it for a moment.
- `web/src/components.tsx`: a star on reference Assets in the Asset list (`list-reference-<id>`) and on the status board (`reference-<id>`).
- `web/src/api.ts`: the `StyleProbe` types. `web/src/styles.css`: the panel.
- Playwright `web/e2e/style.spec.ts` (2 flows, three small rooms measured on `palette`, no sprite): two references, a third's bar out of range with its finding shown and the references beside it; the finding opens the panel, the board marks references, Remove reference takes one out.
- Gaps for the backend, not worked around: the Probe has no `closest` reference, so the UI shows every built reference and names only the furthest; the figure picture is the first frame of `idle` facing `s` read from `finish`'s `render.json` (the Probe doesn't give the path of the frame it measures). A figure and a prop were not exercised in Playwright (only a room); the figure/prop path is the same code with `outline_density` and the `render.json` frame.

Eye check (the Owner, still open): on a character, a sprite and a room, open the Asset on `finish` (room: `palette`), make two others references, and look at the bars and the pictures. Screenshots of the room case: `web/shots/0335-style-scores.png`, `web/shots/0335-style-board.png`.
