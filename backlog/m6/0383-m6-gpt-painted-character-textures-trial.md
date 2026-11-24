---
status: todo
milestone: M6
agent: character-pipeline
type: trial
---

# M6: trial: GPT Image paints a character's texture, and 3D keeps the animation

Spec §2 (principle 3), §6.3 (`model`, `render`), §10 (`gen`, "Spend"). The Owner, 2026-11-24: the GPT Image rooms are the
target and are not to be changed; the characters must reach their level of detail and their palette. Prototype code stays in
`backlog/m6/0383-trial/` or the scratchpad, not in `kiripix/`. Nothing in the art Project is written except through Kiripix
Commands; the trial's own files go in the trial folder.

## The idea

The rooms' detail comes from GPT Image painting. A sprite frame painted by GPT Image would not stay consistent across hundreds
of frames and 8 directions, so it doesn't paint frames. It paints **the Model's texture** once, and the existing pipeline
(`render` → `palette` → `finish`) makes every frame from it, consistent by construction:

1. Render the character large (about 1024 px tall), in its rest pose, **unlit** (Diffuse Color only), from the front, the back
   and both sides, at a flat orthographic camera. Also each view's UV and depth passes, for projecting back.
2. Send each view to GPT Image as an edit, with a room Plate (`annex_bedroom`) as a style reference: paint the same figure,
   same outline and pose, as flat unlit colour in the rooms' style (fabric folds, seams, hair strands, small highlights in the
   colour itself, the rooms' palette feel). **No light and no shadow**: `render` shades it, and a painted shadow would be
   shaded twice. Use `input_fidelity` and a mask of the silhouette.
3. Project each painted view back onto the Model's UV texture in headless Blender (camera projection, the view facing the
   surface most squarely wins, blended at the seams), and save it as a new texture beside the original.
4. Render the usual clips at 51 px with it, through `palette` and `finish`, and compare.

## What to do

1. One character: mc03_female (body only, no Wearable). Steps 1 to 4 above.
2. **The prompt, in ChatGPT, by the Owner** (the Owner, 2026-11-24: free on the subscription, and quick to refine). Put in the
   trial folder the front view, the `annex_bedroom` Plate and two or three prompt wordings, and stop for the Owner. The Owner
   tries them in ChatGPT, refines them there, and puts the results and the winning wording in the trial folder. Nothing in
   this step needs exact alignment: it answers only whether GPT Image paints flat unlit colour in the rooms' style.
3. **Alignment check on the ChatGPT result.** Measure its silhouette drift against the front render (as in step 5). If it
   lines up well enough to project (say so with the figure, and show the projected front on the model), the Owner may make the
   other three views in ChatGPT too, and the trial brings them into the trial folder with no API cost. Otherwise:
4. **The four views through `kiripix gen`**, with the winning wording, the silhouette mask and the Owner's `approve` for each
   call: `gen` sends the view at its own size and maps the result back onto it pixel for pixel, which ChatGPT doesn't. Expect
   4 to 8 calls, about $1 at medium quality; the estimate is printed before each.
   `gen` takes only rooms, Props and portraits (`GEN_KINDS` in `kiripix/core/gen.py`), not a character. Don't change that
   for the trial: import each view as the Source of a scratch Prop (`trial_mc03f_front`, ...) in the art Project, and paint it
   as an edit of its Source with `gen <prop> --state <name> --prompt "..." --reference <plate>` (`--look` is rooms only), so
   the calls are in the art Project's ledger and under its cap. Remove the scratch Props when the trial ends (`kiripix`
   Commands only), and list them in the Result.
5. Measure, on the 1024 px views: how far the repaint's silhouette moves from the render's (px, worst and mean), since that's
   what makes projection seams; and on the 51 px frames: colours used, and whether the detail survives the downscale (the
   colour changes per pixel inside the silhouette, today's against the painted texture's).
6. If 0382 has landed, render with its settings as well; if not, with today's settings. Say which.
7. If it works on the body, try one Wearable (mc03_female_clothes01) the same way, and say whether each Wearable needs its
   own calls or one call can paint the body and its Wearables together.

## What to record, in this ticket

- The prompts tried in ChatGPT and which wording won; which views came from ChatGPT and which from `gen`, and why; the `gen`
  calls (IDs, cost from the ledger).
- The silhouette drift figures and how the projection handled it: seams, the sides, under the arms, the top of the head that
  no view sees squarely.
- A sheet for the Owner, enlarged 4x (nearest), each panel captioned: the original texture and the painted one, and the 51 px
  frames (idle and walk, s, e, n) in `annex_bedroom` and `annex_living_kitchen`, today's against the trial's. Path given here.
- The cost per character (and per Wearable) and the Owner's time per character.
- A recommendation: go (with follow-up tickets: a Command that runs the views, the calls and the projection; where the
  painted texture lives as a Variant; how `render` picks it up and what that does to its input hash), or no-go and why.

## Notes

- This is the first use of GPT Image on characters. [0353](0353-m6-provider-research.md) left character sprites to
  [0354](0354-m6-provider-research-actors.md); this trial uses GPT Image for a texture, not a sprite, and its result goes
  back to 0354 as evidence either way.
- Only `gen` reaches OpenAI. No test calls it (the Owner, 2026-11-23: tests cost $0).

## Acceptance criteria

- [ ] The table, the sheet and the recommendation above, with the Owner's go or no-go recorded.
- [ ] Every `gen` call is in the art Project's cost ledger; total API spend stated (or $0 if every view came from ChatGPT).
