# A room's normal maps are a `normals` Stage before `palette`

**Status: accepted** (by the Owner on 2026-11-20; drafted the same day for ticket 0339. The Owner approved normal maps for painted rooms on 2026-11-18,
after trial 0252. Follows ADR 0004.)

The game's M10 needs a flashlight in its tunnels (its ISS-020): a `PointLight2D` that shades a painted room's walls. That
needs a normal map beside the room's images. Trial 0252 made one from a depth Runner (Depth Anything V2 Small, Apache-2.0)
in about 3 s a room on the GPU and 8 s on the CPU. Walls, ledges and stairs catch the light, and 88.6 % of the walkable
floor stays exactly flat. Its outline put the Stage "after `layers` and `palette`". ADR 0004 says every Runner Stage sits
between `fit` and `palette`, so a palette tweak never asks for a Runner again. This ADR places the Stage and says what it
reads, what it writes and how the Owner corrects it.

## The decisions

1. **A `normals` Stage between `masks` and `palette`.** room: brief → source → fit → layers → masks → **normals** →
   palette → looks → loops → place → reach → export. It reads `layers`, `source`, `fit` and `masks`, and the `[body]`
   setting. Only `export` reads it. `palette` doesn't, so a palette change never rebuilds it, and a change to the normals
   rebuilds only `export`.
2. **Off by default.** `mode` is `off` (the default) or `depth`. With `off`, the Stage is `done` with no output and no
   Runner call. A parameter at its default stays out of the input hash, so adding the Stage rebuilds nothing on an
   existing room. The Owner turns it on per room: the tunnels, not the sunny bedroom.
3. **With `depth`, one pinned depth call.** The Runner reads the Source. Its key is the Source, the call's parameters
   (its input size among them) and the weights hash (ADR 0002). There are no clicks. The Stage maps the depth through the
   Grid transform to target pixels. For each foreground Layer it refills the depth outside the Layer's alpha from inside
   it, so the cut makes no step. Then it applies Sobel, `strength`, a `deadzone` that stays flat, and `levels` per side,
   with 0252's values as the defaults. The result uses Godot's encoding and is never palette-mapped. A Layer or Grid
   change rebuilds it deterministically, with no Runner call.
4. **One image: the room's normal map as seen.** The Stage writes one `normal.png`, the room's size. Each pixel takes
   the normal of its front-most Layer, by the Layers' alpha. A Stage has one image for its Overrides (ADR 0004), so this
   is the image the Owner paints. The Plate's and each foreground Layer's normal maps are that image cut by their alpha,
   at `export`, as `palette` cuts its mapped composite. Under a Layer, the Plate carries the Layer's normals. They're
   hidden while the Layer covers them, as they were in the trial.
5. **The Owner's fix.** A `flatten` Decision (a brush or a polygon, with `erase`) sets the normal inside it to flat,
   facing the camera. An Override paints normals by hand. Both are in target pixels, so they survive a new Runner or new
   weights (spec §8). A `flatten` isn't made on an image and replays as it is. An Override on a changed normal map puts
   the Stage in `needs-review`, as any Override does.
6. **"Flat where walkable" is a Check of `normals`.** `normals.not_flat_walkable` (warning) finds walkable pixels whose
   normal tilts more than a threshold, which 0341 sets from the trial. Its `fix` is a `flatten` over the area. Walkable is
   the glossary's Derived mask, from `solid`, `pit` and the Body. The Stage derives it with the pure Op `place` uses,
   because `place`'s `walkable.png` comes after `normals` in the order. Top view only; side view is Later.
7. **Looks and Loops take the room's normals.** At `export`, a Look's or a Loop's images take the room's normal map cut
   to their box, with no depth call of their own. Their geometry is the room's. A Loop's frames share one normal map, so
   a `sway` moves colour over still normals.

## We considered

- **After `palette`, as 0252 outlined.** The depth call reads nothing `palette` makes, and neither do the Ops after it.
  A Stage that reads `palette` goes stale on every palette tweak. An Override on it would then go to `needs-review` for a
  change that can't affect it. It would also break ADR 0004's rule. A character aligns its normal pass in `finish`,
  after mapping, because its outline adds pixels the pass must cover. A room's `palette` moves no alpha, so there is
  nothing to align.
- **A parameter of `layers`.** `layers` has the Source, the Grid transform and the alpha. But `masks`, `palette`,
  `looks`, `loops` and `place` all read `layers`. Turning normals on, or any `flatten`, would rebuild the room from
  `masks` down. A new depth result would put `layers` in `needs-review` and hold the Layers behind a normal map. And
  `layers`' one image is the Plate, so an Override couldn't paint normals.
- **Normals only at `export`.** `export` would make a Runner call after every other Stage. It has no image for an
  Override and no place for a `flatten`, and there would be no `preview --stage normals`. A depth result waiting for the
  Owner would hold the Godot write, not just the normals.
- **Late in the order, before `export`, with the same edges.** This keeps ADR 0004's real point (no edge from
  `palette`), and `palette` to `reach` build while a depth result waits for the Owner. It wasn't chosen because it amends
  ADR 0004's rule, and it splits a room's Runner reviews between the start and the end of the run. It stays open if
  the stop below proves costly.
- **For the Check, `reach` or `export`, so that `normals` doesn't read `masks`.** Reading `masks` costs no waiting:
  `run` takes Stages in order and stops at the first that can't finish, so `normals` waits for `masks` either way. The
  edge only makes a Mask edit rebuild `normals`, in about 2 s, with no Runner call, and with nothing to do when `mode`
  is `off`. In `reach`, every `flatten` would rerun the floods (1.4–1.7 s on a room with Looks) and put normals into
  reachability. In `export`, the finding would come last, after a full rebuild, on a Stage the Owner doesn't fix it on.
  In `normals`, a `flatten` stroke clears its finding as soon as the Stage rebuilds.

## Consequences

- **A lit room has one more stop.** A new depth result waits for the Owner (`needs-review`, ADR 0002), and `run` stops
  there, before `palette`. In a batch of first passes (0331), each room with `mode = depth` adds one stop to the review
  queue. The Owner may turn `depth` on after the first pass instead.
- **The input size is a recorded parameter.** The Runner's input size (1036 px on the long side, or 518 px) is part of
  the call's key. A smaller size is set or recorded, never chosen silently from the machine's free VRAM, so a pin doesn't
  depend on the machine.
- **Adding the Stage (0341) changes no other Stage's input hash.** Giving `export` the `normals` edge (0342) makes every
  room's `export` stale once. That is a deterministic rebuild, with `export`'s `version` and `room.json`'s
  `schema_version` bumped. A room with `mode = off` exports `normals: null` and its scene unchanged.
- **What each ticket writes.** 0341 writes one `normal.png`. 0342 cuts the Plate's, each Layer's, and each Look's and
  Loop's maps from it.
- **Checks:** `normals.not_flat_walkable` (warning, as above) and `normals.size` (error: the normal map is the room's
  size).
- **Still open:**
  - **A Look that changes geometry**, such as a toppled shelf or a fallen wall. It shows the room's normals under its
    region, and those describe the room before the change. No room needs one yet: R6's power-on Look changes light, not
    geometry. When one does, the likely answer is a depth call on the Look's edit, pinned on the edit at Source
    resolution, as ADR 0009 allows for a region, so a palette tweak still never asks for it again. Where that call
    lives is open.
  - DA3-Small or DA3-Base in place of V2 Small (0340's comparison).
  - Fine relief (cracks, brick): a smooth depth map gives only the room's big forms.
  - Side view: the Check is top view only.
