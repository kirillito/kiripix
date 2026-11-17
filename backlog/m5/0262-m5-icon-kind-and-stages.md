---
status: todo
milestone: M5
agent: imaging-engineer
type: ticket
parent: 0253-m5-icon-kind.md
---

# M5: the `icon` Kind and its Stages

Part of [0253](0253-m5-icon-kind.md), built on its recommendations: one Asset per icon, a Kind of its own, and no atlas. If
the Owner or the game's M08 overturns one, update this ticket before starting.

## What to build

- **The Kind:** `kiripix new icon <name>`, `describe icon`, and `[icon] size` (16, 24 or 32) in `kiripix.toml` (bump
  `schema_version`, with its migration).
- **`brief`:** `size` (the Project's unless set), `padding` (px, default 1, room for the outline), notes.
- **`source`, `cutout`, `palette`, `finish`:** the Prop's Stages, reused, not copied.
- **`fit`:** the Prop's `grid` or `downscale`, onto the square less the padding, centred. The alpha goes to the grid by vote.
  `fit.cropped` and `fit.padded` as the Prop's.
- **Checks:** `icon.size` (exactly the square), binary alpha, the palette.
- `export` is a stub until [0263](0263-m5-export-an-icon.md).

## Acceptance criteria

- [ ] CLI seam: an icon from a fixture image on a flat chroma background builds through `finish` at 16 and at 32, centred,
      with binary alpha, every pixel on the palette.
- [ ] A wrong size is `icon.size`. `new --help` lists `icon`.
- [ ] Contract samples. The glossary's **Kind** lists `icon`. Spec §3 moves it out of "later", and spec §6 gets a short
      §6.6 Icon.
