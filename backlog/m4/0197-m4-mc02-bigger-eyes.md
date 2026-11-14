---
status: done
milestone: M4
agent: none
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0159-m4-part-vanishes-check.md]
---

# M4: mc02's eyes stop vanishing once the Model's eyes are bigger

Spec §6.3 (checks). Moved out of [0159](0159-m4-part-vanishes-check.md), 2026-11-12: 0159 built `sheet.part_vanishes`, but
checking it on mc02 needs the Owner's art Project and a re-modelled Model, which an agent can't make.

## The gap

At 52 px mc02's eyes are about one pixel each and vanish in some frames ([0117](../m3/0117-m3-gate.md)). The Owner's fix is in
the Model: bigger, anime-style eyes, as in Sea of Stars or Chrono Trigger. `sheet.part_vanishes` is how to tell it worked.

Known so far: on a copy of mc02 re-rendered for [0150](0150-m4-palette-ramps-per-part.md) (2026-11-12, with
`parts=skin,hair,jacket+hood,jeans,boots`), `kiripix check` on `finish` gave 15 `sheet.part_vanishes` warnings. That copy was in
a scratch folder, not the art Project.

## What to do

1. **Before:** in the art Project, render mc02 through `finish` and run `kiripix check character.mc02 --json`. Record the
   `sheet.part_vanishes` findings for `eyes` (clip, direction, frames) here.
2. **The Owner** makes the eyes bigger in the Model, takes it through the Mixamo round trip again if the mesh change needs it,
   and imports it.
3. **After:** render and check again. Record the findings here.

## Acceptance criteria

- [ ] Before: the finding lists the frames where the eyes go missing.
- [ ] After the Owner's bigger eyes: no `sheet.part_vanishes` for `eyes`. Any that remain for other materials are listed here,
      each with the Owner's call: fix the Model, raise `height`, or leave it out of `watch_parts`.

## Closed, 2026-11-13: superseded by 0203

Bigger eyes in the Model (tried on mc03) made the eyes vanish less, but they still changed shape in every frame. The fix is
[0203](0203-m4-stamped-eyes-blinks-and-still-clips.md): `finish eyes=stamp` paints each eye as a fixed pattern, so it can't
vanish, and `sheet.part_vanishes` no longer watches the eye materials. The Owner saw the stamped eyes in the game and says
they read as eyes. The before and after counts above weren't recorded, and aren't needed now. `sheet.part_vanishes` findings
for other materials go to whichever character ticket meets them.
