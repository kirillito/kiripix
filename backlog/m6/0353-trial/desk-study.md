# 0353 desk study: steps 1 (draft) and 2

Written 2026-11-20. Steps 3 to 5 have not started; they wait for the Owner's accounts. Nothing was spent, no account was
created, and no key was used or written down. Every vendor page below was fetched anonymously as a public web page.
"Read 2026-11-20" means that day. The `.research/` briefings were not used as sources.

## Step 1: the volume of one year (corrected by the Owner, 2026-11-20)

The first draft (30 rooms, 680 images) is superseded. The Owner's numbers: a pass rate so far of about 1 kept image in 10
generated, so the generations are about 10 times the kept counts.

| Task | Kept per year (Owner) | Used here | Generated at 1 in 10 | Canvas |
|---|---|---|---|---|
| Room Source | 80 to 100 | 90 | 900 | 1376 x 768 (16:9, the brief's default) |
| `extend` piece | 40 to 50 | 45 | 450 | about 1376 x 768 |
| Look edit | 40 to 50 | 45 | 450 | room size |
| Prop state | 60 | 60 | 600 | small |
| Portrait emotion | 80 ("easy on free tiers; maybe leave out") | 80 | 800 | about 160 x 224 |
| Sprite clip or animation | 50 | 50 | 500 | small |
| VFX strip | 30 | 30 | 300 | small |
| **Total** | | **400 kept** | **4,000 generated** (3,200 without portraits) | 1,800 room size, 2,200 small (1,400 without portraits) |

What $100 a year allows: $100 / 4,000 = **$0.025 a generation** ($0.031 without portraits; about 11 generations a day on
average). That is below Nano Banana 2.1's $0.0336 at 1K (4,000 x $0.0336 = $134; 3,200 x $0.0336 = $107), and the price
of every paid candidate below is above it, except GPT-Image at low quality. So a paid route does not fit, or only
just, at 1 in 10. The pass rate is the lever: cost per kept image is the price divided by the pass rate, so a Provider that
keeps 1 in 4 is worth 2.5 times its price. Step 3 must measure the pass rate per Provider, not only the price.

The Owner's rules, for the rest of this study: **$0, no card for anything** (the $5 Gemini prepay is refused); only
Providers with free credits, ideally renewing daily; FLUX is dropped (BFL's API terms let it train on our data and forbid
removing C2PA); C2PA and SynthID loss is fine for Gemini and OpenAI.

## Step 2: the desk table

Prices are per image at the size we need unless said. The "Yearly" column was worked out on the superseded 820-image draft; at 4,000 generations multiply by about 4.9. Round 2 below replaces the verdicts.

### Summary

| Candidate | Price per image | Yearly at 820 | How it is paid | Free for step 3 | Rooms (1376 x 768)? | Verdict |
|---|---|---|---|---|---|---|
| Gemini API, Nano Banana 2.1 (`gemini-nano-banana-2.1`) | $0.0336 at 1K, $0.0504 at 2K | about $28 at 1K (input images add about $1) | prepaid credit, minimum $5, or postpay; no plan | none on the API (see below) | yes, 16:9 at 1K is 1376 x 768 | step 3 |
| Gemini API, Nano Banana 2 (`gemini-3.1-flash-image`) | $0.067 at 1K, $0.101 at 2K | about $55 | same | none | yes | only if 2.1 is worse |
| Gemini API, Nano Banana Pro (`gemini-3-pro-image`) | $0.134 at 1K and 2K | about $110 for everything; about $20 for 150 room Sources only | same | none | yes | room Sources only, if better |
| Gemini API, Nano Banana 2 Lite (`gemini-3.1-flash-lite-image`) | $0.0336 at 1K | about $28 | same | none | yes | not for us: the vendor says it is not optimised for multiple references or multi-turn editing |
| OpenAI image API, GPT-Image-2.5 and 2.6 (Sunburst, Flare) | $30 per million output tokens; per-image figure not readable. GPT-Image-2 at the same rates, 1536 x 1024: $0.005 low, $0.041 medium, $0.165 high | about $17 (rooms medium, small low) to $34 (all medium); high does not fit | prepaid credit; organisation verification may be needed | none stated | yes, any size to 3840 px, multiples of 16 | step 3 (third place) |
| Black Forest Labs, FLUX 3 Image | $0.048 at 1K, $0.07 at 1.5K; Klein $0.009 and $0.011 | $39 to $57; Klein about $7 to $9 | prepaid credits through a card; auto top-up optional | none stated | yes | terms problem, see below |
| fal (host) | Nano Banana 2 $0.08; Nano Banana $0.0398; Nano Banana Pro $0.15 | $65 for NB2 | prepaid; free credits not stated | not stated | yes | dropped |
| Replicate (host) | FLUX 1.1 pro $0.04; FLUX dev $0.025; the rest by GPU second | about $33 | prepaid credit; "select models free, then billing" | not stated | yes | dropped |
| Retro Diffusion | RD Lite $0.05, Core $0.10, Pro $0.18 flat; edit, inpaint, outpaint $0.12; animation $0.10 to $0.25 a run | about $25 to $50 for the 470 small images; rooms not possible | prepaid balance, never expires, from $5 | $0.50 on a new account, no card | no: 512 px on a side (Pro 256) | step 3, small tasks |
| PixelLab | about $0.008 to $0.017 per image, animations $0.016 to $0.04 (estimates, "pricing is provisional") | about $5 of usage, but the plan price is unread | monthly subscription; a pause is not documented | a free trial of limited generations and fewer tools; no card | no: 400 px (pixflux), 512 px (pixen) | held back |
| SpriteBrew | tokens, packs from $4.99 for 500; per-style cost not shown | n/a | token packs, never expire | 5 tokens, then 3 a day, no card | no | dropped |

### Gemini API (Google)

Read 2026-11-20:
[pricing](https://ai.google.dev/gemini-api/docs/pricing),
[image generation](https://ai.google.dev/gemini-api/docs/image-generation),
[Nano Banana 2.1 model page](https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1),
[Nano Banana 2 Lite model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-image),
[billing](https://ai.google.dev/gemini-api/docs/billing),
[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits),
[additional terms](https://ai.google.dev/gemini-api/terms).

- Price: output images are $30 per million tokens for 2.1, so $0.0336 per 1K image (1120 tokens), $0.0504 per 2K, $0.113
  per 4K. Input is $1.50 per million (text, image, video). The Pro page says an input image is set at 560 tokens, about
  $0.0011; I assume the same for 2.1, which its page does not state. Batch is half price but slower.
- **No free tier on the API for any image model.** Every image model's row says "Free Tier: Not available". Google AI Studio
  (the Owner's baseline UI) is free, and its unpaid use trains Google's products. So step 3 for this candidate is not
  possible at $0: the account needs a billing account linked and a prepaid balance of at least $5. I found no free trial
  credit on the pages read.
- Billing: new accounts start on the Free tier; Tier 1 needs a linked billing account; prepaid minimum $5; spend caps
  exist per project and per tier (Tier 1 cap $250), monthly, not yearly.
- API: image and text in, image and text out; up to 14 references (2.1: up to 10 object images and 4 characters; Pro: 6
  objects, 5 characters, 3 style references); editing with an input image; "inpainting" by conversational semantic masking
  (the model is told what to change; there is no mask file); aspect ratios include 16:9 = 1376 x 768, 21:9 = 1584 x 672, 3:2,
  4:3, 1:4, 4:1, 1:8 and 8:1; 1K, 2K and 4K; thinking levels; the model does not always give the number of images asked
  for. I found no seed or repeatability setting on the pages read. Batch size per call: not stated. Rate limits: per-tier
  image limits (IPM) exist but the numbers are in a browser-rendered table I could not read. Latency: only the Lite page
  gives a figure (under 2 seconds, a vendor claim); not measured.
- Terms: "Google won't claim ownership over that content" but may generate the same or similar content for others. Paid
  Services: prompts and responses are not used to improve products; logged for a limited time for abuse checks. Unpaid:
  used to improve products and read by human reviewers. Users must be 18 or older. Developing competing models is not
  allowed. **Every output carries an always-on SynthID watermark** (invisible), with C2PA named on the Lite page. Kiripix
  re-encodes and quantises every import, so C2PA metadata would not survive; whether SynthID does is not known. The terms
  page I read does not forbid removing them.
- `gemini-2.5-flash-image` is deprecated and shuts down 2027-03-15, so it is excluded.

### OpenAI image API

Read 2026-11-20: [pricing](https://developers.openai.com/api/docs/pricing),
[image generation guide](https://developers.openai.com/api/docs/guides/image-generation),
[GPT-Image-2 model page](https://developers.openai.com/api/docs/models/gpt-image-2),
[GPT-Image-2.5 Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst),
[your data](https://developers.openai.com/api/docs/guides/your-data),
[rate limits](https://developers.openai.com/api/docs/guides/rate-limits).
`openai.com/api/pricing` and `openai.com/policies/service-terms` and `/business-terms` answered 403 to an automated fetch
and were not read; the developers.openai.com pages were.

- Models now: GPT-Image-2.6 and 2.5 (each Sunburst for detailed work and Flare for fast iteration); `gpt-image-2` is marked
  Deprecated. Rates: image output $30 per million tokens, image input $8 per million, text input $5 per million. The
  per-image figure comes from a calculator I could not run. The only per-image table is the historical one, for
  `gpt-image-2` at 1536 x 1024: $0.005 low, $0.041 medium, $0.165 high (1024 x 1024: $0.006, $0.053, $0.211). The 2.5 and
  2.6 models use the same token rates, but "equal token rates don't mean equal cost per image", so the yearly figure is an
  estimate. Batch is half price.
- API: generate and edit; several reference images; a mask file for edits (masking is "entirely prompt-based": the model
  decides what to do with the mask area); markup-guided edits on 2.5 and 2.6; any WIDTHxHEIGHT in multiples of 16 with a ratio
  between 1:3 and 3:1, up to 3840 on an edge and 655,360 to 8,294,400 pixels (above 2560 x 1440 is experimental on 2.5), so
  1376 x 768 is allowed; transparent PNG or WebP background; SVG and animated GIF output on 2.6. No seed is documented on
  the page. Latency: complex prompts may take up to 2 minutes. OpenAI names a limitation: the model may struggle to keep
  recurring characters consistent across generations.
- Rate limits: the GPT-Image-2 page lists 20 images per minute on the Build tier and 150 on Launch. The rate-limits page
  shows a Free tier with a "$100 / month" usage limit, but I could not tell whether image models are open to it. The image
  guide says API Organization Verification may be needed before using GPT Image models.
- Terms: data sent to the API is not used to train or improve models unless the Owner opts in. Ownership of the output:
  the terms page was not readable, so it is not confirmed from the vendor.
- Free credits: none stated on the pages read.

### Black Forest Labs, FLUX API

Read 2026-11-20: [pricing](https://bfl.ai/pricing), [docs pricing](https://docs.bfl.ml/quick_start/pricing.md),
[credits and billing](https://docs.bfl.ml/account_management/credits_billing.md),
[FLUX 3 Image](https://docs.bfl.ml/flux_3/flux3_image_overview.md),
[technical parameters](https://docs.bfl.ml/guides/prompting_unified_technical.md),
[Developer Terms](https://bfl.ai/legal/developer-terms-of-service),
[API Service Terms](https://bfl.ai/legal/flux-api-service-terms),
[Terms of Service](https://bfl.ai/legal/terms-of-service).

- Price: credits, 1 credit = $0.01, shared by the Playground and the API. FLUX 3 Image $0.041 (768 x 768), $0.048 (1K,
  "about 1 megapixel"), $0.07 (1.5K, "about 2 megapixels"), $0.10 (2K), $0.607 (4K). FLUX 3 Image Klein (5.6B, open
  weights) $0.008 to $0.036. FLUX.2 [pro] $0.03 for the first megapixel. FLUX.1 Kontext [pro] $0.04. A request is billed at
  the smallest tier with at least as many pixels, so 1376 x 768 (1.06 MP) is $0.048 or $0.07 depending on how "about 1
  megapixel" is applied; I show both.
- API: text to image; edit by instruction; up to 10 references; bounding-box layout and local edits; 15 fixed ratios from
  21:9 to 9:21, or `auto` (follows the first input image; an edit keeps the input's frame); exact `width` x `height` from
  256 to 6256 per side, up to 16.8 MP (4 MP with references); a polled result URL. No seed on the pages read. Rate
  limits: the terms forbid exceeding "reasonable request volume"; no numbers read.
- Billing: a card through Stripe; auto top-up is optional; the minimum purchase was not read. Free credits: none stated.
- Terms: the Developer Terms say the Owner owns the Output and may use it commercially. The API Service Terms also grant
  BFL a perpetual, irrevocable licence to the Owner's inputs and outputs "to train and improve" its models, and I found
  no opt-out for the API (the consumer terms offer one by e-mail). The Developer Terms forbid removing Content Credentials
  (C2PA metadata), and Kiripix's import re-encodes every image. Both are for the Owner to decide.

### fal and Replicate (hosts)

Read 2026-11-20: [fal pricing](https://fal.ai/pricing), [Replicate pricing](https://replicate.com/pricing),
[Replicate billing](https://replicate.com/docs/topics/billing).

- fal sells the Google models above the vendor's price: Nano Banana 2 $0.08 against Google's $0.067 at 1K; Nano Banana
  Pro $0.15 against $0.134; Nano Banana $0.0398 against $0.039. It also lists open models, cheap but with no instruction
  editing (Z Image Turbo $0.005 per megapixel, FLUX.1 schnell $0.003 per megapixel). No free credits are stated on the page.
- Replicate lists FLUX 1.1 pro $0.04, flux-dev $0.025, flux-schnell $3 per thousand, Ideogram v3 quality $0.09 and Recraft v3
  $0.04; most models are billed by GPU second. "You can run select models on Replicate for free, but after a bit you'll be
  asked to set up billing."
- Dropped: they are middlemen. Their only use would be one key for many models, and `gen` will have one adapter per vendor
  anyway. They cost more than the vendor for the same model, and Replicate's list on that page is the older FLUX 1 and
  Ideogram generation. They can come back if a model we want exists only there.

### Retro Diffusion

Read 2026-11-20: [home](https://www.retrodiffusion.ai/), [pricing](https://www.retrodiffusion.ai/pricing), and the
vendor's own repository [api-examples](https://github.com/Retro-Diffusion/api-examples) (its `README.md` and `llms.txt`;
the README says the hosted guide at `retrodiffusion.ai/app/guide/api` is the source of truth, and I could not fetch it).
The vendor's terms page (`/terms`) is browser-rendered and returned no text, so **terms, ownership, training and rate
limits are not confirmed**.

- Price: flat per image at any size: RD Lite $0.05, RD Core $0.10 (16 styles, up to 9 references), RD Pro $0.18, RD Mini
  from $0.03; Advanced Animations from $0.10 a run (most $0.14, Subtle Motion and Custom Action $0.25), 4 to 16 frames,
  looping, transparent background, sheet export; image edit, inpaint and outpaint $0.12 (limited to 256 px); background
  remover $0.01; Pixel Art Fixer $0.002 standard and $0.005 neural. Failed generations are refunded. The balance never
  expires; $50 or more gets a 10% bonus. A VFX animation style exists (24 to 96 px, square).
- API: REST v2, key in the header `X-RD-Token`, made by the Owner on the vendor's developer-tools page (up to 5 keys); a
  free `check_cost`; a seed; `input_image` with `strength`; `reference_images`; inpainting with a mask image; asynchronous
  jobs; an MCP server. **The largest size is 512 x 512 (RD Core), 256 for RD Pro and the edit tools, so rooms at 640 x 360
  or 1376 x 768 are impossible; portraits, sprites, props and VFX fit.** The vendor's own craft guide suggests 96 to 128 px
  for portraits and says generation from references "re-imagines" rather than converts.
- Free: new accounts get $0.50 with no card, "enough for 10 RD Lite images or 5 RD Core images". That is a taste, not the
  step 3 set for animation ($0.14 a run) and portraits; a $5 top-up needs a card.
- It draws in its own style and palette, so Kiripix's `palette` Stage still applies. Whether it sits next to the painted
  rooms and the 52 px 3D sprites is what step 3 would answer.

### PixelLab

Read 2026-11-20: [API page](https://www.pixellab.ai/pixellab-api), [FAQ](https://www.pixellab.ai/docs/faq),
[terms of service](https://www.pixellab.ai/termsofservice), [`llms.txt`](https://www.pixellab.ai/llms.txt),
[refund policy](https://www.pixellab.ai/refundpolicy). The plan and pricing page is browser-rendered and was not
readable, so **the monthly plan prices and the generations per plan are not confirmed.**

- Per-call estimates (the page says "estimates, pricing is provisional"): create image 64 to 400 px about $0.008 to $0.013;
  512 px about $0.017; animate with text v3 up to 256 px, 4 to 16 frames, $0.022 to $0.042; normal map $0.0065 to $0.0077;
  background removal about $0.006.
- It is a subscription ("a subscription is the most consumer-friendly method"; "you can stop using the product any time"),
  and a newer animation tool needs "Tier 1 subscription or higher". Whether a plan can be paused for months is not said.
  Under the ticket's rule that is the question to settle before any sign-up.
- Max sizes 200 to 512 px, so no rooms. It offers characters, animation, portraits, tilesets, a VFX page and inpainting.
- Terms: "You own the copyrights to your creations", commercial use allowed, no training other models on the output; it does
  not train on inputs or outputs and does not store images unless stated. Programmatic use only through its own API,
  with a token from the account page.
- Free: "Try for free, no credit card required", with a limited number of generations and fewer tools. Whether the free trial
  includes the API is not said.
- Held back from step 3: no room-size work, a subscription, and unreadable plan prices. It would be a strong candidate
  for sprites and animation if the Owner reads the plan price and a pause is possible, because it is the cheapest per call.

### SpriteBrew

Read 2026-11-20: [home](https://www.spritebrew.com/), [terms](https://www.spritebrew.com/terms).

- Dropped. It is a web app (open source, AGPL-3.0) with 5 animation styles and token packs from $4.99, and I found no
  public API. Its terms say "Don't attempt to reverse-engineer, scrape, or abuse the API" and "Don't use automated tools
  or bots to generate content in bulk", which `gen` would break. Sprite sheets only, so no rooms.

### Not studied

Ideogram, Recraft, Stability, Seedream and Qwen-Image on fal. Midjourney was not checked. The ticket named the candidates
above; add any of these only if the Owner wants.

## What I could not read

- OpenAI: the per-image price of the 2.5 and 2.6 models (browser calculator); the service terms (403).
- Gemini: the per-tier image rate limits (browser table); whether a seed exists.
- BFL: the minimum credit purchase; rate limits; seed; any API opt-out of training.
- Retro Diffusion: terms, ownership, training, rate limits.
- PixelLab: plan prices, generations per plan, whether a plan can be paused, the free trial's contents.
- fal and Replicate: free credits, terms.

## Round 2 and the recommendation

The first-round recommendation (Gemini API prepay, Retro Diffusion top-up, OpenAI card) is withdrawn by the Owner
answers of 2026-11-20 ($0, no card). Round 2, the new recommendation and the closing option are in
[desk-study-round2.md](desk-study-round2.md).
