---
status: done
milestone: M6
agent: ml-engineer
type: trial
---

# M6: research: which image Provider, within $100 a year? The shared study, and painted images

Spec §16, open decision 5 ("Which API provider comes first"; Nano Banana is the candidate), §14 ("Generation and agents,
deferred"), §8 and §10 (`gen`, `cost`, `[providers]`). Written on 2026-11-20 after the research briefings in `.research/`,
which favoured a local model; the Owner decided against one for now (an RTX 2070 can't run the 8 GB FLUX builds well, and
setup and upkeep cost the Owner's time). Prototype code stays in `backlog/m6/0353-trial/` or the scratchpad, not in
`kiripix/`.

**Two tickets.** This one does the work every kind of Asset shares (the volume, the desk study, the budget) and tests the
**painted images**: rooms and their `extend` pieces, Looks, Props and their states, portrait emotions and cutscene stills.
[0354](0354-m6-provider-research-actors.md) tests the **actors**, NPCs and enemies as sprites with their animations, from
this ticket's desk table. VFX strips are a route of [0347](0347-m6-vfx-trial.md), and image-to-3D Providers are
[0144](0144-m6-image-to-3d-trial.md)'s; both read this ticket's desk table for those candidates. The $100 a year is one
budget for all of them.

## Why

The Owner's aim, once a Provider is chosen: from the game repo, Claude writes a room's prompt (the brief, [0348](0348-m6-brief-renders-the-prompt.md)),
Kiripix sends it to the Provider, the Owner sees the Variants and picks one or asks for a regeneration or a changed prompt;
then Claude runs `extend` through the Provider (canvas, generate, `add`, repeat, `done`), and the Owner approves the joined
room. The same loop makes Props, Looks, Prop states, portrait emotions and NPCs. The Owner's hand work in the image model's
UI goes, and the game's story and dialogue become what sets the pace.

## The question

Which cloud Provider (or two, one per kind of work) makes consistent, in-style results for the game's art, has an API
Kiripix's `gen` can call, has terms that fit a game that may be sold, and fits **$100 a year** at the Owner's volume? And for
painted images, is any of them clearly better than the baseline, Nano Banana's own UI on its free tier (1376 x 768, the
brief's default canvas)?

## Rules

- **$0 for the research.** Free tiers, free credits and trial credits only. If a candidate needs a card on file for its free
  credits, ask the Owner before signing up. No paid plan, not even for a month.
- **The Owner makes the accounts** and gives API keys through environment variables. A key is never written to the Project,
  the ticket, a log or a test. The agent never creates an account.
- Every figure from the desk study (price, limits, terms) is read from the vendor's own page, with the date read and the link.
  The `.research/` briefings are leads, not sources.
- Free credits are few: spend them in the order of the test set below, and stop a candidate early once it clearly fails.

## What to do

1. **The volume,** for the whole game's art, with the Owner and the game's backlog: a
   year's work per task, and the regenerations each takes (from the Owner's experience in the UI so far):
   - painted: room Sources, `extend` pieces per room, Look edits, new Props, Prop states, portrait sets and emotions,
     cutscene stills;
   - actors (for [0354](0354-m6-provider-research-actors.md)): new NPCs and enemies, their directions and clips, one-off poses;
   - VFX strips (for [0347](0347-m6-vfx-trial.md)) and image-to-3D concepts (for [0144](0144-m6-image-to-3d-trial.md)).

   **Cutscenes, first:** ask the Owner what the game's cutscenes need as art. Its scenes run in the engine (the scene runner,
   dialogue, room changes, scenes inside battles), so the art is likely stills at the game's resolution (an
   illustrated moment), the cast's one-off poses (0354) and Looks. Record the answer here; it sets the cutscene task below.

   This turns $100 a year into a number of images per task.
2. **The desk study.** For each candidate, one row:
   - price per image at the size we need (or per credit, and credits per image), and the yearly cost at step 1's volume;
     whether it's pay-per-use, prepaid credits, or a monthly plan that can be paused (a plan that can't be paused rarely fits
     $100 a year);
   - API: image in and out, editing with an input image (the canvas of `extend`, the Source for a Look), masks or regions,
     several reference images for style and for a character's identity, the largest output size and aspect ratios,
     transparent or flat-colour backgrounds, seed or other repeatability, batch size, rate limits, latency;
   - what it offers beyond images: sprite directions, animation from a frame, image-to-3D, video;
   - terms: who owns the output, commercial use, whether it trains on our inputs or outputs, whether free-tier outputs are
     public, visible or invisible watermarks, limits on automated use of the API;
   - the free tier or credits available for the tests.

   Candidates to check, at least: the Gemini image API (Nano Banana and its successors), OpenAI's image API, Black Forest Labs'
   FLUX API, pay-per-use hosts of open models (fal, Replicate), the pixel-art services Retro Diffusion, PixelLab and SpriteBrew,
   and the image-to-3D services 0144 names (Meshy, Tripo). Add any the study finds; drop one with a short reason.
3. **The painted test set,** the same inputs for every candidate that survives step 2 and makes painted images, from the art
   Project (copied to a scratch Project, so the art Project isn't touched):
   - a room Source from a first-chapter room's brief prompt (a street room's or a dungeon room's), 4 Variants;
   - one `extend` piece from that room's canvas (`extend <id> canvas`), 2 Variants;
   - one Look edit of the street room ("keep everything the same except": a lamp off), 2 Variants;
   - one new Prop (a newspaper box on a flat chroma background, with a first-chapter room as the style reference), 2 Variants, and one
     Prop state (a bin toppled, from the bins' Source);
   - one portrait emotion from a neutral portrait;
   - one cutscene still, as step 1's answer defines it (for example two main characters in the street room at night, with their
     portraits as references for who they are), 2 Variants.
4. **Score with Kiripix,** importing the results into the scratch Project, not by eye alone:
   - room Source and `extend` piece: whether `extend add` registers (its residual), the palette mapping error after
     `palette`, and the style measures from [0332](0332-m6-style-match-trial.md) against the first chapter's rooms, if they're ready;
   - Look edit: `look.misaligned`, `look.drift` (count and boxes), `look.unchanged`;
   - Prop and Prop state: `cutout` (does the chroma key take it whole), the `fit` and `palette` findings, the style measures
     beside the bins;
   - emotion: `portrait.misaligned`, `portrait.residual`, the `fit` and `palette` findings;
   - cutscene still: the palette mapping error and style measures as a room's, and whether the cast is recognisable (the
     Owner's call);
   - consistency: how much the Variants of one prompt differ from each other in the same measures;
   - the Owner's call: how many of each task's Variants the Owner would keep, and the Owner's minutes per task.
5. **The automation loop,** on the best candidate only, as a prototype script outside `kiripix/`: brief prompt → Provider → import
   → the Owner's pick → canvas → Provider → `extend add`, for one 2-screen room. Record where it broke, what it cost and the
   Owner's minutes, beside 0134's 25 minutes of hand work for four pieces.

## What to record, in this ticket

- The volume and the cutscene answer (step 1).
- The desk table (step 2), with links and the dates read.
- The scores (step 4) per candidate and task, with the result images' paths for the Owner.
- The cost per year at step 1's volume, per candidate.
- A recommendation per painted task: a Provider, or "keep using the UI and the inbox" ([0350](0350-m6-source-inbox.md)).
- **The joint plan,** once 0354 (and 0347, 0144 if they use a Provider) have reported: which Providers, for which tasks, and
  that their yearly cost together fits $100.

## Out of scope

Building the Provider adapter, `gen`, the cost ledger and the budget cap (spec §4's `budget_usd_month` is a monthly cap;
$100 a year may want a yearly one), and `gen` driving `extend`. They are follow-up tickets, written from the recommendation.

## Acceptance criteria

- [ ] The volume estimate and the cutscene answer, agreed with the Owner.
- [x] The desk table, every figure linked to the vendor's page with the date read.
- [ ] The scores and images for the candidates that reached step 3, and the step 5 loop on the best one.
- [ ] The joint plan across 0353 and 0354 within $100 a year, and the Owner's choice, with the change to spec §16 decision 5
      (and §8 or §14 if needed) listed for the main session.
- [ ] Follow-up tickets filed, with `agent:` and `depends_on`: at least the Provider adapter with `gen` and the cost ledger,
      `gen` driving `extend`, and [0143](0143-m6-gen-a-look-edit.md) updated to the chosen Provider.
- [x] $0 spent; any sign-up that needed a card was the Owner's yes first (no sign-up so far).

## Result in progress (2026-11-20): steps 1 and 2 done, round 2 after the Owner's answers

Full text with every figure's link and the date read: [0353-trial/desk-study.md](0353-trial/desk-study.md) (step 1, round 1) and
[0353-trial/desk-study-round2.md](0353-trial/desk-study-round2.md) (free credits only). $0 spent; no account created; no key used.

**The Owner's answers (2026-11-20):** (1) the volume is 80 to 100 room Sources, 40 to 50 `extend` pieces, 40 to 50 Look edits, 60
Prop states, 80 portrait emotions, 50 sprite clips, 30 VFX strips a year, at a pass rate of about 1 in 10; (2) no $5 Gemini
prepay, $0 and no card for anything; (3) only Providers with free credits, ideally daily; (4) C2PA and SynthID loss is fine for
Gemini and OpenAI; FLUX direct is dropped because its API terms forbid removing C2PA and let BFL train on our data.

- **Step 1 (agreed):** about 400 kept and 4,000 generated a year (3,200 without portraits). $100 a year is $0.025 a generation
  ($0.031 without portraits). Nano Banana 2.1 at $0.0336 a 1K image would cost $134 ($107), so a paid route does not fit at 1 in 10.
  Cost per kept image is price over pass rate, so step 3 must measure the pass rate.
- **Step 2, free credits:** the Gemini API has no free image tier (pricing page: "Not available" for every image model), and the
  $300 Cloud welcome credit cannot pay for it on accounts opened after 2026-03-02; free Gemini image generation is the AI Studio UI
  only. PixelLab has a one-off limited trial, not a daily credit; animation on the free tier is not confirmed by its pages. The one
  candidate with a daily-renewing free API quota is **Cloudflare Workers AI**: 10,000 Neurons a day, resetting 00:00 UTC, FLUX.2 klein
  4B at 256 to 1920 px with up to 4 input images and a seed, about 50 to 90 room-size images a day, no training and zero retention.
  Open licence point: its FLUX models cite BFL's terms. Pollinations has a free-able balance of unknown size and public output
  URLs. Krea's free plan is about 4 images a day with commercial rights tied to the plan.
- **Recommendation:** a reduced step 3 on Cloudflare klein 4B only; the Owner needs a free Cloudflare account (no card; stop if it asks),
  an API token, the account id, env vars `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`, and a decision on the BFL licence
  reading. If klein 4B does not reach the bar, close the trial with "keep using the UI and the inbox
  ([0350](0350-m6-source-inbox.md))". No follow-up tickets are filed yet; if filed they start at 0365.

### The Owner's answers to round 2 (2026-11-20)

- **Cloudflare Workers AI, FLUX.2 klein 4B: yes,** a reduced step 3 on it. The Owner makes the free account (stop if it asks
  for a card), a Workers AI API token and the account id, in `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. Step 3 runs in a
  later session, once they're set.
- **klein 4B's licence:** acceptable **for the trial only** (Cloudflare hosts it with zero retention). No FLUX model enters
  Kiripix until the Owner confirms a commercial licence.
- **Pass rates per task** (replacing the flat 1 in 10): room Sources about 1 in 10 to 20; Looks and Props about 1 in 3 to 5.
  Step 1's generation counts and step 3's bar (kept per generated image, by task) use these.
- Pollinations only if Cloudflare fails (round 2's recommendation, not asked again).


## Result: closed by the Owner's decision (2026-11-23)

**The painted work goes to OpenAI's GPT Image, through the OpenAI API, on a budget of $10 a month** (`[providers]
budget_usd_month = 10` in the art repo's `kiripix.toml`, replacing the earlier $0 rule and this ticket's $100 a year). The Owner
chose it from use, not from this study: round 2 had closed OpenAI as paid-only (`desk-study-round2.md`), and the Cloudflare
klein 4B step 3 was never run. **Steps 3 to 5 are waived.** The evidence there is:

- Round 1's desk row ([desk-study.md](0353-trial/desk-study.md), read 2026-11-20): `gpt-image-2` at 1536 x 1024 costs $0.005
  low, $0.041 medium, $0.165 high, about $17 to $34 a year at step 1's volume, at the flat 1-in-10 pass rate; the per-image
  price of 2.5 and 2.6 wasn't readable. At the round-2 pass rates for room Sources (1 in 10 to 20), medium quality may not
  fit $120 a year; the cap ([0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md)) holds it either way, and `gen`'s
  ledger will give the real figures.
- [0377](0377-m6-extend-joins-a-re-rendered-strip.md): a real GPT Image `extend` piece of the street room joins at 0.66 px
  (`--max-residual 1`), seam difference 3.3, no visible seam. GPT Image re-renders the kept strip, so its pieces need the
  raised limit.

**Tasks:** room Sources, `extend` pieces, Look edits, Props and their states, and portraits with their emotions (the Owner:
"generating character portraits seems OK for now"). **Not decided:** character and enemy sprites and their animations, which
stay with [0354](0354-m6-provider-research-actors.md); VFX strips ([0347](0347-m6-vfx-trial.md)) and image-to-3D
([0144](0144-m6-image-to-3d-trial.md)) are unchanged. No FLUX model enters Kiripix (round 2's licence answer stands).

**Spec:** §16 decision 5 and the §14 line on the image API Provider name OpenAI's GPT Image.

**Follow-up tickets:** [0379](0379-m6-openai-provider-and-gen.md) (the OpenAI Provider, `gen`, the cost ledger and `cost`),
[0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md) (the estimate and the cap, on 0379),
[0380](0380-m6-gen-drives-extend.md) (`gen` driving `extend`), and [0143](0143-m6-gen-a-look-edit.md) moved to OpenAI.
