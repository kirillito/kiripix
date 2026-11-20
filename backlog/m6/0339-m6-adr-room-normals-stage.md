---
status: todo
milestone: M6
agent: reviewer
type: adr
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: ADR: a room's normal maps are a `normals` Stage before `palette`

Spec §6.1, §8 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). The Owner approved normal maps
for painted rooms from a depth Runner on 2026-11-18 ([0252](../m5/0252-m5-environment-normals-trial.md), "The Owner's
verdict"), for the game's M10 (a flashlight in the tunnels; the game's ISS-020). Draft the ADR and the spec change; the work
tickets are [0340](0340-m6-depth-runner.md) to [0343](0343-m6-ui-room-normals.md).

## What the ADR settles

- **Where the Stage sits.** 0252's outline put it "after `layers` and `palette`". ADR 0004 says every Runner Stage sits
  between `fit` and `palette`, so a palette tweak never invalidates a Runner call. The depth Runner reads the Source through
  the Grid and the Layers' alpha, and its output is never palette-mapped, so the proposal is
  **brief → source → fit → layers → masks → normals → palette → looks → loops → place → reach → export**. `normals` reads
  `masks` only for its Check ("flat where walkable"). Say whether the Check should instead live in `reach` or `export`, so
  that `normals` doesn't wait on `masks`.
- **Off by default.** A `mode` parameter, `off` (the default) or `depth`. With `off`, the Stage is `done` with no output, and
  a parameter at its default stays out of the hash, so no existing room rebuilds or calls a Runner. The game turns it on per
  room (its tunnels, not its sunny bedroom).
- **Looks and Loops.** A Look's or a Loop's pieces take the room's normals cut to their box (the geometry is the room's), not
  a depth call of their own. Say whether a Look that changes geometry (a toppled shelf) needs its own later, and record
  that as open.
- **The Owner's fix.** A `flatten` brush or polygon Decision sets the normal to flat (facing the camera) inside it, and an
  Override paints a normal by hand. Both are in target pixels, so they survive a new Runner (spec §8).

## Acceptance criteria

- [ ] `docs/adr/0014-…` drafted, with the alternatives (after `palette`; a parameter of `layers`; normals only at `export`)
      and why they lost.
- [ ] Spec §6.1's Stage line and table, §8's depth row and §14 updated to match, marked "proposed" until the Owner accepts.
- [ ] The Owner's acceptance recorded here, with the date.
