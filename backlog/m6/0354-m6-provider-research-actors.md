---
status: todo
milestone: M6
agent: ml-engineer
type: trial
depends_on: [0353-m6-provider-research.md]
---

# M6: research: can a Provider make the game's NPCs and enemies, as sprites with their animations?

Spec §16, open decision 5, §6.4 (the `sprite` Kind), §6.3 (characters from 3D) and §14 ("PixelLab: delayed, because its
sprite generation has been unsatisfactory so far"). The actors' half of [0353](0353-m6-provider-research.md), which does the
volume, the desk table and the $100-a-year budget for both; start once its desk table (step 2) is done. Prototype code stays
in `backlog/m6/0354-trial/` or the scratchpad, not in `kiripix/`. Same rules as 0353: $0, free credits only, the Owner makes
the accounts, keys only in environment variables, every figure from the vendor's own page.

## Context

- The cast is rendered from 3D: the mc03 bodies at 52 px, 8 directions (the game's DEC-068), the `top34_8` camera at a
  30° look-down for every character source (DEC-054), and NPC variants made from a base with no new render
  ([0336](0336-m6-npc-variants-from-a-base.md)). Battle clips use 4 facings (DEC-048).
- Actors that aren't humans on a base, such as the raccoons, come in as `sprite`s from 2D frames. PixelLab was the route and
  was delayed: its sprites were unsatisfactory, and its view control too weak to hold the 30° camera (DEC-044, ISS-021).
- The game needs, for chapter 1 and after: background NPCs (its M17), enemies such as the raccoons and the Waiting Ones
  (provisional: silhouettes that wake as you pass), bosses, and one-off poses for cutscenes (an edit of a character's frame,
  imported as a one-frame clip; spec §1, non-goals).

## The question

For each kind of actor, which route gives the Owner a usable, in-style actor for the least money and time: a Provider's
sprites and animations through the `sprite` Kind, a Provider's concept image into image-to-3D ([0144](0144-m6-image-to-3d-trial.md))
and the character recipe, or the 3D route alone (a base with layers and ramps, 0336)? And can any Provider hold one actor's
identity across 8 directions and the frames of a clip, at the 30° camera, beside the 3D cast?

## What to do

1. **The Owner's account of PixelLab's failure:** what was wrong (identity drift, the angle, the size, the palette,
   the animation), so every candidate is tested for it.
2. **Candidates,** from 0353's desk table: those that offer directions or animation from a frame (PixelLab, SpriteBrew or
   Retro Diffusion, and any other the study found), and the general image models, asked for a sheet of directions or frames
   with a reference image.
3. **The actor test set,** the same inputs for each candidate, with a frame of an mc03 body at `top34_8` and the raccoon
   sprite as the references for the angle, the size and the style:
   - a background NPC from a text description: one frame in 8 directions, then a walk of 4 to 8 frames in them;
   - an enemy: a raccoon variant (another colour or a hat) with an attack and a hit in 4 facings;
   - a non-human or odd one: a Waiting One (a silhouette that wakes), idle and wake;
   - a one-off pose for a cutscene: an edit of an mc03 frame (surprised, pointing), 2 Variants.
   Where a candidate can't do a step, it records that and moves on.
4. **Score with Kiripix,** each result imported as a `sprite` in a scratch Project (`import --role sheet`, then `frames`,
   `fit` in `downscale` mode to 52 px, `palette` by parts, `finish`, `sheet`):
   - `frames.direction_missing`, `frames.frame_count`, `fit.grid_differs`, `fit.alpha_partial`, `fit.height`,
     `sheet.pivot_drift`, `palette.off_palette`;
   - identity: the frames and directions where the actor changes (clothes, proportions, colours), counted by the Owner;
   - the angle: whether the actor reads as the 30° camera beside an mc03 body;
   - the style measures from [0332](0332-m6-style-match-trial.md) against the mc03 bodies and the laneway, if they're ready;
   - the Owner's minutes per actor to a usable sheet, including fixes, and the credits spent.
   Note every gap in the `sprite` Kind the imports show (a naming rule a service's export needs, a frame layout `frames`
   can't cut), as a candidate follow-up ticket.
5. **The 3D comparison:** for the background NPC, the cost of the same actor from a base (0336: the Owner's minutes and the
   render time), and, if 0144 has a result, from image-to-3D.

## What to record, in this ticket

- PixelLab's failure, in the Owner's words.
- The scores per candidate and actor, with the GIFs or sheets' paths for the Owner, beside an mc03 body.
- A recommendation per kind of actor (background NPC, enemy, non-human, cutscene pose): a Provider, image-to-3D, the 3D route
  alone, or hand work; with its yearly cost at 0353's volume, for 0353's joint plan.

## Acceptance criteria

- [ ] PixelLab's failure recorded, and every candidate tested for it.
- [ ] The scores and sheets for each candidate that reached step 3.
- [ ] The recommendation per kind of actor, with its cost, handed to 0353's joint plan.
- [ ] The `sprite` Kind's gaps the imports found, filed as follow-up tickets with `agent:` and `depends_on` if the Owner
      takes the route.
- [ ] $0 spent; any sign-up that needed a card was the Owner's yes first.
