---
status: done
milestone: M6
agent: none
type: spec
depends_on: [0354-m6-provider-research-actors.md, 0385-m6-sprite-zip-states-are-clips.md]
---

# M6: PixelLab as a Provider, for sprites and their animations

The Owner approved PixelLab on 2026-11-25, after [0354](0354-m6-provider-research-actors.md), with **$15 a month for all Provider
calls, OpenAI and PixelLab together** (`[providers] budget_usd_month` in the art Project, was $10). Spec §8, §10 ("Spend"), §14
and §16 (open decision 5). Child tickets: [0387](0387-m6-pixellab-provider-jobs-and-operations.md) to
[0391](0391-m6-pixellab-keyframe-motion-for-objects.md).

## Problem Statement

0354 made the game's raccoon, black squirrel, animal services worker and pigeon with PixelLab, through a throw-away script
(`0354-trial/pixellab.py`, `keypoints.py`), and brought them into Kiripix by `import --role sheet`. That works, but outside
Kiripix: the script has its own $10 cap and ledger, the art Project's `budget_usd_month` sees none of PixelLab's spend, an agent
can spend without the Owner's `approve`, a character's PixelLab ID lives in `notes.md`, and each pose's ZIP is cut and repacked
by hand. The next poses the game needs (more of its ticket 0106, the birds' take-off, battle facings) should be one `gen` each,
behind the same approval, budget and ledger as OpenAI's.

## What 0354 showed is worth calling

| Operation | Endpoint | What for | Cost (2026-11-25) |
|---|---|---|---|
| A character from our frames | `create-character-v3` with `reference_image` and `direction_images` | Gives PixelLab the actor as drawn (the worker came back pixel-identical), so states and motion keep its pixels and its size | about $0.001 (0.25 generations) |
| A character from text | `create-character-v3` with `description` and `image_size` | A new actor (the raccoon, the squirrel, the pigeon) | $0.026 to $0.031 at 32 px |
| A state | `create-character-state` | A pose in 8 directions in one call (hop, swipe, hurt, crate_open) | $0.075 up to 84 px |
| Motion by PixelLab's own rig | `estimate-custom-skeleton`, then `animate-with-skeleton-v3` with `write_motion_frames` | The animals' walks and pecks | about $0.005 + $0.011 (4 frames) or $0.016 (8) a direction |
| Motion from a render | `animate-with-skeleton-v3` with `keypoints` per frame (mc03's clip through `render`'s `points`, retargeted) | The humans' walks | about $0.016 a direction |
| An image | `generate-image-v2` | A prop or a one-frame figure (the crate with a raccoon), 25 to 64 candidates a call | $0.08 |

**Not called:** text-driven motion from one frame (`animate-with-text-v3` without a last frame, and `characters/animations` in `v3`: it melts faces, the Owner dropped it; with two frames of an object's own, ticket 0391 calls it),
`.../mirror` (never mirrored, spec §6.4). The image URLs in answers refuse downloads, and the terms let code call `api.pixellab.ai`
only, so results come as the character's ZIP (`GET /characters/{id}/zip`, free) or as the job's base64 images.

## Solution

**`gen` paints a sprite through PixelLab** (open decision 1, the Owner, 2026-11-25). The same Command, the same pending call,
`approve`, budget, daily limit and ledger; new targets for a sprite Asset, each stored as a sheet in `src/sheets/` that the
`frames` Stage already reads:

| Command | Operation | Stored |
|---|---|---|
| `gen sprite.x --prompt "<who>" [--canvas 32]` | a character from text, in the sprite's `directions` | its rotations as a sheet: clip `idle` |
| `gen sprite.x --prompt "<who>" [--canvas 32] [--view V]` | (the same, with the camera's view) | as above |
| `gen sprite.x --from-frames [--from idle] [--view V]` | a character from the sprite's own frames (`frames` output, the clip's first frame per direction; south at least): the facings it lacks by `generate-8-rotations-v3`, then `create-character-v3` from all of them ([0390](0390-m6-pixellab-one-image-to-a-sprite.md)) | the made facings with the sent frames as drawn, as a sheet under the next free name (`idle_2`); none when every facing is there; the character ID |
| `gen sprite.x --image --prompt "<what>" [--style <asset>[:<clip>] \| --style <png>] [--canvas N] [-n N]` | `generate-image-v2`, styled after another Asset's frames or a PNG (0390) | Variants; `pick` stores the chosen one as a one-direction sheet, clip `idle` |
| `gen sprite.x --state hop --prompt "<the pose>" [--canvas 64]` | a state of the sprite's character | the new state's rotations as a sheet: clip `hop` |
| `gen sprite.x --clip walk --motion rig --prompt "<the action>" [--frames 8] [--directions s,e,n,w] [--from idle]` | PixelLab's own rig and motion, per direction | the frames as a sheet: clip `walk` |
| `gen sprite.x --clip walk --motion skeleton --render character.y [--render-clip walk]` | keypoints from a character's `render`, retargeted onto the sprite ([0389](0389-m6-pixellab-skeleton-motion-from-a-render.md)) | the frames as a sheet: clip `walk` |
| `gen sprite.x --clip topple --motion keyframes --from <clip> --to <clip> --prompt "<the action>" [--frames N]` | `animate-with-text-v3` between two of the sprite's own frames, only for a sprite marked `faces = false` ([0391](0391-m6-pixellab-keyframe-motion-for-objects.md)) | the frames as a sheet: clip `topple` |
| `gen prop.x --provider pixellab --prompt ...` | `generate-image-v2`, the plain image call | Variants, as OpenAI's |

**Decisions (made here; the Owner may overturn any):**

- **A sheet per call, holding only what the call made.** A state's ZIP holds every state of the group, rejected tries included
  (0354), so core keeps only the new state's folder, repacked in PixelLab's own layout (`<state>/rotations/<direction>.png`,
  `animations/<clip>/<direction>/frame_NNN.png`), so the naming rule reads it unchanged and no Stage changes (no `version` bump).
  The whole answer is kept for the record in the call's folder under `.kiripix/calls/sent/`, never a Source.
- **A retry is a new name, not a replacement.** A second `--state hop` sends `state_name` `hop_2`, as PixelLab does on its site,
  so both are clips and the Owner keeps one with the `sheet` Decision's renames and `leave_out` (0385). Nothing is overwritten.
- **The character is kept with the Asset:** `asset.toml` gains an optional `[sprite.pixellab]` table: `character_id`, its
  `canvas`, and how it was made (`frames` or `text`); since 0390 the camera's `view` (`high top-down` by default, set when
  the character is made, sent by every endpoint that takes it) and since 0391 `faces` (true by default; `kiripix set <sprite>
  pixellab faces=false` is the Owner's mark that allows `--motion keyframes`). The table made `asset.toml` `schema_version` 2. States and motion need it; `gen --state` without one is
  `gen.character_needed` with the `fix` `gen <id> --from-frames` (or `--prompt` when the sprite has no frames). The state
  prompts are already in the Asset's call history, so a pose can be added later at the same size.
- **One approval for a whole operation.** A clip in 4 directions is 4 jobs, and the rig and skeleton routes put an estimate call
  before them. One pending call holds the operation's whole plan (its jobs, in order, each with its endpoint and estimate), the
  estimate is their sum, and `approve` sends them all. A failed or cancelled job stops the rest; each job sent is its own ledger
  line, and the directions that came back are stored.
- **Jobs wait on the cancel token.** A Provider can't import core, so `call` is given a `wait(seconds)` that core binds to
  `kiripix.core.cancel.sleep`. Polling is every 5 s, then 10 s; a cancel `DELETE`s the job (free while queued) and the ledger
  records the job at its estimate, as for OpenAI.
- **Charges in USD or generations.** Every answer's `usage` is `usd` or `generations`. The ledger keeps both (`usd`, priced for
  the cap; `generations`, as charged), and generations count toward the cap at the price table's dated rate per generation.
- **The price table is per endpoint and canvas,** dated, in the Provider's file, as OpenAI's is. PixelLab says its prices "vary
  with GPU time", so the ledger's charge, not the estimate, is what counts once known.
- **Terms** (open decision 2, the Owner, 2026-11-25): the Provider carries a `terms` line, as a Runner carries its licence:
  "output is the Project's for commercial use; no training of models on it; code may call only api.pixellab.ai". `describe gen`
  and `cost` show it. Each sheet a call stores is recorded in `imported.jsonl` with the Provider and the call ID, so its origin is
  traceable. Nothing enforces it.
- **Key:** `PIXELLAB_API_KEY` in the Project's `.env`, as `OPENAI_API_KEY` is.
- **The cap until it lands:** PixelLab's spend before 0388 (0354's $2.61, all in November 2026) stays outside the ledger; the
  month ends on 2026-11-30.

## User Stories

1. As the Owner, I want every PixelLab call to wait for my `approve`, with its estimate, so that an agent never spends on its own.
2. As the Owner, I want PixelLab's and OpenAI's spend under one monthly cap, so that $15 means $15.
3. As the Owner, I want a pose added to a sprite in one command, landing as a clip I can keep or leave out, so that I never
   repack a ZIP by hand.
4. As the Owner, I want a walk made from mc03's walk for a human sprite, and from PixelLab's own rig for an animal, so that each
   gets the route 0354 found best.
5. As the Owner, I want a cancelled call to stop PixelLab's job, so that a mistake costs nothing while it's queued.

## Child tickets

Budgets in tokens.

| Ticket | What | Agent | Depends on | Budget |
|---|---|---|---|---|
| [0387](0387-m6-pixellab-provider-jobs-and-operations.md) | The Provider: jobs with `wait` and cancel, operations with inputs that aren't images, ZIP and frame results, `usage` in USD or generations, the price table, `terms`; `generate-image-v2` through the plain `call` | ml-engineer | — | 150–250k |
| [0388](0388-m6-gen-paints-a-sprite.md) | Core: `gen` for a sprite (`--prompt`, `--from-frames`, `--state`, `--clip --motion rig`), one pending call for an operation's jobs, a sheet per call, `[sprite.pixellab]`, the ledger's generations, the contract and the spec | core-engineer | 0387 | 200–350k |
| [0389](0389-m6-pixellab-skeleton-motion-from-a-render.md) | `--motion skeleton`: keypoints from a character's `render` `points`, retargeted onto the sprite (0354's `keypoints.py` made Kiripix code) | ml-engineer | 0388 | 100–180k |
| [0390](0390-m6-pixellab-one-image-to-a-sprite.md) | (added later) a sprite from one image (`--image`, `--style`), its other facings from south alone, the camera's `view` | core-engineer | 0388 | 150–250k |
| [0391](0391-m6-pixellab-keyframe-motion-for-objects.md) | (added later) `--motion keyframes`: an object's clip between two of its frames, `faces` | core-engineer | 0388 | 80–140k |

**Total: about 0.45–0.78M tokens** for 0387 to 0389, 0.68–1.17M with 0390 and 0391. No gate ticket and no UI ticket: approval stays in the Owner's terminal (0381), and the UI
has no pending-call panel yet.

## Testing Decisions

- **CLI seam** with a fake PixelLab transport, as OpenAI's (`openai-requests/`): every request kept as JSON, jobs that queue,
  complete, fail and are cancelled, a ZIP with several states. No test reaches `api.pixellab.ai`; the harness drops
  `PIXELLAB_API_KEY` from the environment as it drops `OPENAI_API_KEY`.
- The keypoint mapping and the retarget are pure functions, tested directly on a small `render.json` fixture.
- New and changed Commands have samples in `tests/cli/test_contract.py`.

## Out of Scope

- Text-driven motion from one frame (`animate-with-text-v3` without a last frame, `characters/animations` `v3`), mirroring, video to frames.
- A UI panel for pending calls and the month's spend (0381's follow-up, still the Owner's call).
- Environmental loops (no route was tested in 0354) and the pigeon's take-off (the game's backlog).
- Palette steering (`color_image`, `target_palette`): Kiripix's `palette` Stage fits the frames afterwards, as in 0354.

## Result

Done 2026-11-27: every child ticket (0387 to 0391) is done, and each user story has a CLI test (approval only from the Owner's
terminal, one ledger and cap, a pose as a clip, both walk routes, a cancel that deletes the queued job). Left for follow-up
tickets, from 0390's trial: `--from-frames` takes no description (PixelLab gets the Asset's name), and `frames` raises
`frames.direction_missing` on a south-only sprite yet builds.
