---
status: done
milestone: M6
agent: ml-engineer
type: trial
depends_on: [0353-m6-provider-research.md]
---

# M6: research: can a Provider make the game's animals and minor actors, as sprites with their animations?

Spec §16, open decision 5, §6.4 (the `sprite` Kind), §6.3 (characters from 3D) and §14 ("PixelLab: delayed, because its
sprite generation has been unsatisfactory so far"). The actors' half of [0353](0353-m6-provider-research.md). Prototype code
stays in `backlog/m6/0354-trial/` or the scratchpad, not in `kiripix/`. The Owner makes the accounts and buys the credits;
keys only in environment variables; every figure from the vendor's own page.

**Since 0353 closed (2026-11-23):** the painted work went to OpenAI's GPT Image, on $10 a month for all Provider calls
(`[providers] budget_usd_month`, replacing $100 a year). Portraits and their emotions are in that decision. **Still open
here:** the animals' and minor actors' sprites and their animations.

**Money (the Owner, 2026-11-25):** this trial may spend up to **$15** in all, PixelLab credits and GPT Image together. PixelLab
is used through its API on prepaid credits ($1 = 1 credit), not a subscription, unless step 2's tier check shows the
animation endpoints need one; then the Owner decides on a month's subscription.

## Context

- The cast is rendered from 3D: the 3D bodies at 52 px, 8 directions, the `top34_8` camera at a
  30° look-down for every character source, and NPC variants made from a base with no new render
  ([0336](0336-m6-npc-variants-from-a-base.md)). Battle clips use 4 facings.
- Actors that aren't humans on a base, such as the quadrupeds, come in as `sprite`s from 2D frames. PixelLab was the route and
  was delayed: its sprites were unsatisfactory, and its view control too weak to hold the 30° camera.
- **What the game needs now (the Owner, 2026-11-25):**
  - the **quadruped**, animated;
  - **rodents**;
  - **uniformed workers** (humans);
  - **birds and other ambient life** that make a scene feel alive (small birds, small environmental loops).
  **Crowd NPCs** come from the 3D models (a base with layers and ramps, 0336), not from this trial. **Later, not in this
  trial:** silhouette enemies that wake as you pass, bosses, and one-off cutscene poses (an edit of
  a character's frame, imported as a one-frame clip).
- **Prior art (read 2026-11-25).** Others have the same problem; none of them targets 8 directions at a top-down camera,
  and there's no code to take (Kiripix already has the chroma key, `fit`, `palette` and grid detection). What to take is
  their techniques and failures:
  - [Wombo](https://github.com/acatovic/ai-game-studio) (MIT) and its [dev log](https://community.openai.com/t/ai-game-studio-dev-log-by-platypus/1397035):
    one GPT Image call makes all four views on a 2×2 template image, on a flat green backdrop, which holds identity better
    than a call per view. Its sheet prompt says "Rotate the character; do not horizontally flip a view" and "Keep every
    asymmetric feature attached to the same anatomical side". Motion comes from a **video model** (MiniMax Hailuo,
    Seedance: a 2 to 5 s clip from a start frame, and an end frame for a loop or a transition), then ffmpeg keys and
    extracts the frames and the Owner keeps 12 to 24. A whole sheet of frames in one call, and each frame chained from the
    last, both gave "heavy misalignment and quirky movements". No pixel grid or palette; accessories are fixed by hand.
    By 2026-11-17 its author mostly draws his sprites himself and uses the tool for ideas.
  - [Developing sprite sheets with gpt-image-2](https://community.openai.com/t/developing-sprite-sheets-with-gpt-image-2/1379831):
    the most reliable route reported is **pose transfer from a mannequin** (#1, #5, #19): the pose as image 1, the character
    as image 2, "transfer the pose WITHOUT MIRRORING", with left and right named per limb. Left/right limb swaps persist
    (#1, #6, #13); a video movement costs about $0.25 (#39, a user's estimate); the edits endpoint's moderation can drop
    most outputs, fixed by "non-sexual" in the prompt (#33). OpenAI's curated `hatch-pet` skill (#26) makes Codex's pet
    sprites with gpt-image-2; not read yet.
  - [PerfectPixel](https://github.com/gykim80/perfectpixel-studio) (MIT): 5 directions generated and 3 mirrored, which is
    wrong for the 30° camera and asymmetric actors; a magenta key and a strip of N poses on one ground line.
  - Kiripix already renders any base in 8 directions at `top34_8` for every clip, so a mannequin for pose transfer is free:
    the angle and the pose, PixelLab's two failures, come from 3D, and the Provider only paints the look. A frame painted
    per call still drifts across frames, which is why [0383](0383-m6-gpt-painted-character-textures-trial.md) paints the
    texture once instead; pose transfer suits actors with few frames or no base mesh to texture.
- **PixelLab's API (read 2026-11-25, `https://api.pixellab.ai/v2/openapi.json` and its price list).** Bearer token; long
  calls return a `background_job_id`, polled at `GET /v2/background-jobs/{id}` every 5 to 10 s, cancelled with `DELETE`
  (free while queued). Every response's `usage` says whether it charged `usd` or `generations`; `GET /v2/balance` gives both.
  Prices are PixelLab's estimates, which "vary with GPU time". What matters here:
  - **The camera:** only a `view` enum, `low top-down` (about 20°) or `high top-down` (about 35°), which PixelLab itself
    calls a weak control. No 30°. The angle has to come from frames we give it.
  - **Frames we give it:** `POST /v2/create-character-v3` takes a south `reference_image` and `direction_images` for the
    other 7, used as drawn (a full set imports for 0.25 generations); `create-character-with-8-directions` takes frozen
    `directions` references ($0.0173 at 64 px). `animate-with-text-v3` and `animate-pixminimax` start from our
    `first_frame`, with an optional `last_frame` to close a loop. `POST /v2/save-to-asset` writes our own frames back into a
    character's direction.
  - **Animation:** `POST /v2/characters/animations` (`mode` `v3`: `action_description`, `frame_count` 4 to 16, even;
    `template` with `template_animation_id`; `pixminimax`, "Tier 1 subscription or higher"), one job per direction:
    v3 $0.0129 a direction for 4 frames at 64 px. `POST /v2/animate-with-skeleton-v3` (beta): a `first_frame` and
    `keypoints` per frame (3 to 15 frames), joints as fractions of the image with a `z_index`, a `template_id`
    (`mannequin`, `bear`, `cat`, `dog`, `horse`, `lion`) or a custom `rig` of 2 to 64 joints (each `near`, `mid` or `far`);
    priced by frame count, $0.0513 for 8. `POST /v2/estimate-skeleton` ($0.005) finds a sprite's joints.
  - **Palette:** `color_image` with `force_colors`, or `target_palette` (2 to 256 hex colours, `max_colors`), on the
    character and animation calls.
  - **Not used:** `POST /v2/characters/{id}/animations/{group}/mirror` (it flips a direction, wrong for asymmetric actors).
  - **Terms:** the output is ours for commercial use; no training models on it; code may call only `api.pixellab.ai`.
  - **Its output is native pixel art** at the canvas size, not a large image to downscale; step 4 checks what `fit` does
    with it.

## The question

For each actor the game needs now, which route gives the Owner a usable, in-style actor for the least money and time: a
Provider's sprites and animations through the `sprite` Kind, or the 3D route (a base with layers and ramps, 0336)? And can a
Provider hold one actor's identity across its directions and the frames of a clip, at the 30° camera, beside the 3D cast?

## What to do

1. **The Owner's account of PixelLab's failure:** what was wrong (identity drift, the angle, the size, the palette,
   the animation), so every candidate is tested for it.
2. **PixelLab first,** through its API, by a script in the trial folder that keeps each call's request, response and
   `seed` as JSON beside the PNGs it saved. **The tier check, before more than $5 of credits is bought:** one call to
   `POST /v2/animate-with-text-v3` at 32 px with 4 frames (about $0.022) and one to `POST /v2/characters/animations` in
   `v3`; a 403 means animation needs a subscription, and the Owner decides. Two routes, each tested:
   - **Text-led motion:** the actor made a PixelLab character from our frames where we have them (`direction_images`),
     animated in `v3` (or `template`), with the 3D bodies' ramps or the quadruped sprite's colours as `color_image`.
   - **Motion from Kiripix:** `animate-with-skeleton-v3` with `keypoints` per frame. For the humans, the keypoints are the
     3D body rig's joints in each frame of a clip, projected through the `top34_8` camera by a Blender script in the trial
     folder (the character pipeline's area: if it's more than a small script, the Owner is told, and it may be its own
     ticket). For the animals, a `cat` or `dog` template or a custom `rig`, started from `estimate-skeleton` on the
     actor's frame and moved by the script.
   **Then pose transfer** with GPT Image, within the same $15: a render at `top34_8` in the pose as image 1 and the actor's
   reference as image 2, one frame or direction per call, left and right named per limb; and one call for a sheet of
   directions on a grid template image (3×3, the centre empty), against a call per direction.
   No candidate mirrors a direction to make another. Other services from 0353's desk table (SpriteBrew, Retro Diffusion)
   only if PixelLab and pose transfer both fail.
   **Not tested: video to frames** (a video model's clip, its frames extracted). At about $0.25 a movement it's too dear
   for this trial (the Owner, 2026-11-25).
3. **The actor test set,** the same inputs for each candidate, with a frame of a 3D body at `top34_8` and the quadruped
   sprite as the references for the angle, the size and the style:
   - **the quadruped** (from its sprite): a walk in 8 directions; an attack and a hit in 4 facings;
   - **a rodent** (from a text description, the quadruped as the style): an idle and a run in 8 directions, and one
     action of its own the Owner names (foraging, a climb, an attack);
   - **an uniformed worker** (a human at 52 px): a walk in 8 directions and one action the Owner names (a net or a
     catch-pole), by the skeleton route on the 3D bodies' clips, beside the same worker from a base (step 5);
   - **ambient life:** a small bird (an idle loop of pecking and hopping, and a take-off) in 2 to 4 facings, and one
     environmental loop the Owner picks (a flag, leaves, steam), as a closed loop from a `first_frame` and `last_frame`.
   Where a candidate can't do a step, it records that and moves on.
4. **Score with Kiripix,** each result imported as a `sprite` in a scratch Project (`import --role sheet`, then `frames`,
   `fit` to the actor's height (52 px for the worker; the quadruped sprite's for the animals), `palette` by parts, `finish`,
   `sheet`). PixelLab's frames are native pixel art: say which `fit` mode takes them without resampling, and whether that
   is a gap.
   - `frames.direction_missing`, `frames.frame_count`, `fit.grid_differs`, `fit.alpha_partial`, `fit.height`,
     `sheet.pivot_drift`, `palette.off_palette`;
   - identity: the frames and directions where the actor changes (fur, clothes, proportions, colours), counted by the Owner;
   - the prior art's failures, counted per sheet: left/right limb swaps, a lost accessory, chroma fringe after the key, a
     mirrored asymmetric detail, and the calls the moderation refused;
   - the angle: whether the actor reads as the 30° camera beside a 3D body;
   - the style measures from [0332](0332-m6-style-match-trial.md) against the 3D bodies and a painted street room, if they're ready;
   - the Owner's minutes per actor to a usable sheet, including fixes, and the money spent (from each response's `usage`).
   Note every gap in the `sprite` Kind the imports show (a naming rule a service's export needs, a frame layout `frames`
   can't cut), as a candidate follow-up ticket.
5. **The 3D comparison:** the uniformed worker from a base (0336: the Owner's minutes and the render time), beside
   the skeleton route's worker.

## What to record, in this ticket

- PixelLab's failure, in the Owner's words.
- The tier check's answer: credits alone, or a subscription.
- The scores per candidate and actor, with the GIFs or sheets' paths for the Owner, beside a 3D body.
- A recommendation per actor (quadruped, rodent, uniformed worker, birds and ambient loops): a Provider and
  which route, the 3D route, or hand work; with its cost per actor and per year at 0353's volume. Crowd NPCs stay on the 3D
  route unless the worker's comparison says otherwise.
- If PixelLab is taken: what a Kiripix Provider for it needs that `kiripix/providers/base.py` lacks (keypoints as an input,
  async jobs that can be cancelled, charges in generations as well as USD), as a follow-up ticket.

## Progress (2026-11-25, Claude; nothing spent)

**The test set is the game's real need (the Owner, 2026-11-25):** to waste nothing, the trial makes the poses of the game's
a game ticket: the quadruped's hop, swipe, hurt
and dazed; the rodent's idle, leap and bite; the worker's sack_open, bag and walk; and a sack with a quadruped (a
prop). Each pose is made first as a PixelLab *state* of the existing character (`create-character-state`, 8 directions a
call, 0106's route), imported into the art Project's real `sprite` assets and exported. The other routes run on the same
poses: text-led animation (walks and runs, as extras), the skeleton route (the 3D bodies' walk and downward attack retargeted onto
the existing worker sprite: `keypoints.py --retarget`), and GPT Image pose transfer (the worker's bag at the 3D bodies' 30°, and a
rodent sheet from the quadruped's directions). So step 3's set becomes 0106's list plus the bird and an ambient loop;
the quadruped's attack and hit are 0106's swipe and hurt.

The trial's tools are in [0354-trial/](0354-trial/), with the Owner's run book in its [README](0354-trial/README.md):
`pixellab.py` (every endpoint above, each call's request, response, job and PNGs kept under `runs/`, a ledger from each
`usage`, a $10 cap for PixelLab leaving $5 of the $15 for GPT Image, `--dry-run`), `keypoints.py` and `pose_inputs.py`.
Tested offline only: dry runs, and a local fake of the API (jobs, images, the ledger, the cap, a 402). Not one real call yet.

- **No Blender script is needed for the skeleton route.** `render`'s `points` parameter (ticket 0237) already projects
  named bones through `top34_8` in every frame; `keypoints.py` turns those into PixelLab's 18 joints. Mixamo's rig has no
  nose, eye or ear bones: those 5 come from the render's `eyes` and the head's bones, roughly; a $0.005 `estimate-skeleton`
  on one frame checks the mapping and which side PixelLab calls RIGHT.
- **The quadruped doesn't fit 32 px** (48x52 on its 64 canvas), so the tier check's first call runs at 64 px, about $0.10.
- **The `sprite` Kind's `fit mode = grid` (the default) already takes PixelLab's native pixel art**; `downscale` is for GPT
  Image's frames. Whether `grid` handles the API's frames as it does the website's ZIP is for step 4.
- For the animals' skeleton route the first try is PixelLab's own rig (`estimate-custom-skeleton`) with the motion written
  by PixelLab (`write_motion_frames`), not one moved by a script; a scripted quadruped rig only if that fails.

## Result (2026-11-25)

**The Owner approved PixelLab as a Provider** ([0386](0386-m6-pixellab-provider.md)), within $15 a month for OpenAI and PixelLab
together, and the four actors' import and export.

Spent: **$2.61 on PixelLab** ($2.39 of the $5 left), plus about 25 trial generations, $0 on GPT Image. Records: [0354-trial/](0354-trial/) (`notes.md`
has every call, `runs/` the requests and images; the sheets and GIFs are beside them).

- **PixelLab's failure, in the Owner's words:** "It took me a lot of generations to get quadruped or service worker that was
  fitting our parameters. No animations at free tier was also very limiting."
- **The tier check: credits alone are enough.** The animation endpoints answered 200 on trial generations, and again on prepaid
  credits ($0.011 to $0.016 a direction for the skeleton route). No subscription was needed for anything below.
- **What made it fit:** a character imported from frames we already have keeps their pixels and their size (the worker:
  pixel-identical; a rodent scaled to 20 px and imported: its poses stay at that size, where a 27 px source's grew to 55 px).
  A state takes the whole actor into a pose in 8 directions. Canvas up to 84 px costs the same ($0.075), so leave room.
- **Tries:** 13 state calls gave 8 kept poses (the sack pose is superseded by the crate), about 1 in 1.6, not 0353's 1 in 10.
- **Routes:** skeleton (the 3D bodies' motion retargeted, `keypoints.py`, no Blender script) is the best for the worker, and PixelLab's
  own rig (`estimate-custom-skeleton`, motion written by PixelLab) for the animals. Text-driven animation fails (faces melt,
  ears and stripes change) and is dropped.
- **Kiripix:** `fit` mode `grid` takes the frames at scale 1 with no resampling; 5 poses x 8 directions, only `info` findings.
  The quadruped and worker read beside the 3D bodies after `palette` and `finish`. Gaps: [0385](0385-m6-sprite-zip-states-are-clips.md).
- **Crate, not sack:** the Owner's decision; the game's docs and strings were changed (game repo, uncommitted).

| Actor | Recommendation | Cost |
|---|---|---|
| Quadruped | PixelLab: text once, states for poses, its own rig for the walk | about $0.4 for 5 poses, $0.08 for a 4-direction walk |
| Rodent | PixelLab, idle scaled to size and imported | about $0.2 |
| Uniformed worker | PixelLab from the Owner's frames; skeleton with the 3D bodies' clips for walks | about $0.2 plus $0.065 a clip |
| Birds | PixelLab, its own rig (one bird tried) | about $0.07 an action in 2 directions |
| Environmental loops | not tested | |

At 0353's 50 sprite clips a year, about $0.12 a kept pose or $0.02 a direction: roughly $6 to $10 a year. The Owner's minutes
weren't measured.

**In the art Project and exported to the game:** the quadruped sprite (idle, hop, swipe, hurt, dazed, walk 8 frames; the old sheet's
ZIP removed), the worker sprite (idle, crate_open, bag, walk 4 frames), the rodent sprite (idle, walk, attack and summoned,
8 frames each by its own rig; leap and bite poses),
the crate sprite (candidate 13), all 8 directions but the crate; `palette orphan_size=0` on all four (the default removed
eyes and tail rings). The game's content check passes; the look at 1x in a painted street room is the Owner's.

**Waived by the Owner (2026-11-25):** step 5 (the 3D worker: the PixelLab worker is in the game), the Owner's minutes per actor
(Claude did the work), pose transfer, and an environmental loop (the bird is the ambient life). The bird's take-off goes to
the game's backlog. **Not done:** 0332's style measures. **Weak:** the rodent's walk barely moves its legs except in n and w
(the game hops creatures by tween; a retry is about $0.13). The quadruped's attack and hit are poses, not clips.

The game records the decision in its own log.

**If PixelLab is taken, what a Kiripix Provider needs beyond `kiripix/providers/base.py`:** inputs that aren't images (a
character ID, keypoints, a rig); an answer that is a job to poll and cancel (`DELETE`, free while queued); a result that
isn't a list of images (a character's ZIP); and charges in generations as well as USD. That is [0386](0386-m6-pixellab-provider.md).

## Acceptance criteria

- [x] PixelLab's failure recorded, and every candidate tested for it.
- [x] The tier check done before more than $5 of credits was bought.
- [x] PixelLab's two routes tested, then pose transfer, or the reason one couldn't be (skipped by the Owner).
- [x] The scores and sheets for each actor in step 3, per candidate (`0354-trial/notes.md`; the waived ones above).
- [x] The recommendation per actor, with its cost, handed to 0353's joint plan (closed there; the budget is now shared).
- [x] The `sprite` Kind's gaps the imports found, filed as follow-up tickets with `agent:` and `depends_on` if the Owner
      takes the route.
- [x] At most $15 spent in all, from each response's `usage`; any subscription was the Owner's yes first.
