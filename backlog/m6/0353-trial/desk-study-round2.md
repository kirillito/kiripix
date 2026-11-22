# 0353 desk study, round 2 (2026-11-20): free credits only, no card

All pages read 2026-11-20. Step 1's corrected volume is in [desk-study.md](desk-study.md). The Owner's rules: $0 and no card for
anything (the $5 Gemini prepay is refused); only Providers with free credits, ideally renewing daily; FLUX direct from BFL is
dropped (its API terms let it train on our data and forbid removing C2PA); losing C2PA or SynthID is fine for Gemini and OpenAI.

## Does Google give any free image quota through the API?

No, from Google's own pages.

- [Pricing](https://ai.google.dev/gemini-api/docs/pricing): every image model's row (Nano Banana 2.1, Nano Banana 2, Nano Banana Pro,
  Nano Banana 2 Lite, and the deprecated Nano Banana) says "Free Tier: Not available".
- [Billing](https://ai.google.dev/gemini-api/docs/billing): a new key is on the Free tier, which reaches only "certain models, up to
  the free-tier rate limits"; those limits are shown only on AI Studio's own rate-limit page (a signed-in page I cannot read).
  Together with the pricing page, an AI Studio key gets no image generation.
- Vertex and the $300 welcome credit: the billing page says an account opened after 2026-03-02 cannot spend the $300 Google Cloud
  welcome credit on the Gemini API or AI Studio. The [Google Cloud free page](https://cloud.google.com/free) gives the credit to
  new Cloud customers, who need a billing account (a card). Out under "no card".
- Free image generation exists in the **AI Studio UI** ("Google AI Studio usage is free of charge in all available regions", the
  pricing page's notes), which the Owner already uses. The [terms](https://ai.google.dev/gemini-api/terms) say unpaid use is used to
  improve Google's products and may be read by human reviewers.

## Does PixelLab give free daily credits, and animation on the free tier?

- [FAQ](https://www.pixellab.ai/docs/faq): a free trial "with a limited number of generations", and "only the tools that are the easiest
  to use are included". The code is in a video. The FAQ does not call it daily-renewing, and I found no daily credit on the pages
  read. It does not list which tools are left out.
- [API page](https://www.pixellab.ai/pixellab-api): the PixMiniMax animation tool is marked "Tier 1 subscription or higher, beta". The
  other animation endpoints carry no tier label. So the Owner's "no animation on the free tier" fits the pages but is not confirmed by
  them. The trial is one-off, not renewing. Not usable at $0 for a year.

## Candidates with free credits, at our sizes

| Provider | Free quota | Renews? | API or UI | Sizes | Card? | Verdict |
|---|---|---|---|---|---|---|
| **Cloudflare Workers AI** | 10,000 Neurons a day on the Free plan | **yes, daily, 00:00 UTC** | **REST API**, Workers binding, a playground | FLUX.2 klein 4B 256 to 1920 px a side, up to 4 input images, seed | not stated for the Free plan | **step 3** |
| Pollinations | a balance of "Quest balance + paid balance"; Quests add to it "without a credit card"; the amount is not on the pages read | not stated | REST API (key from its dashboard) and a web app | flux.2-klein-4b, flux.1-schnell, flux.1-kontext-pro and Microsoft mai-image-2.7 are not flagged paid-only | "without a credit card" | second choice, the Owner checks the balance |
| Krea | Free plan: 100 units a day | yes, daily | web UI; an API exists, its price and free access not read | Nano Banana 2.1 costs about 25 units, so about 4 a day | no card | not for us: about 4 images a day, and commercial use depends on the plan |
| Retro Diffusion | $0.50 at sign-up | no, one-off | API | 512 px at most | no card | a taster only |
| PixelLab | limited trial generations | no | plugin, API (seems subscription) | 400 to 512 px | no card for the trial | out |
| Gemini API, Vertex | none for images | | | | | out |
| OpenAI | no Free-tier row for GPT-Image (the rate table lists Build, Launch, Grow; Build means $5 bought) | | | | | out: paid |
| Hugging Face Inference Providers | Free users: no monthly credits (PRO gets $2); credits must be bought | | | | | out |
| Together AI | "Calling image models requires a positive credit balance" | | | | | out |
| Leonardo | API credits are bought apart from the app plans; the free app tier could not be read (terms and pricing pages 403 or 404) | | | | | out for the API; unread |
| fal, Replicate | none stated | | | | | out |
| Ideogram | page returned 403, unread | | | | | unread |
| FLUX 3 direct from BFL | none | | | | | dropped by the Owner |

Links: [Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/),
[limits](https://developers.cloudflare.com/workers-ai/platform/limits/),
[data usage](https://developers.cloudflare.com/workers-ai/platform/data-usage/),
[FLUX.2 klein 4B](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/) and its
[launch note](https://developers.cloudflare.com/changelog/2026-01-15-flux-2-klein-4b-workers-ai/),
[klein 9B](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-9b/),
[Lucid Origin](https://developers.cloudflare.com/workers-ai/models/lucid-origin/),
[Pollinations API reference](https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md),
[its image model list](https://gen.pollinations.ai/image/models),
[Krea pricing](https://www.krea.ai/pricing), [Krea terms](https://www.krea.ai/terms),
[Hugging Face pricing](https://huggingface.co/docs/inference-providers/pricing),
[Together serverless models](https://docs.together.ai/docs/serverless-models),
[Leonardo API start](https://docs.leonardo.ai/docs/getting-started),
[OpenAI GPT-Image-2 rate limits](https://developers.openai.com/api/docs/models/gpt-image-2).

## Cloudflare Workers AI in detail

- **Free quota:** "10,000 Neurons per day at no charge"; "All limits reset daily at 00:00 UTC"; past it, requests "fail with an error"
  on the Free plan (more needs Workers Paid). So an accidental bill is not possible on the Free plan. The page does not say whether
  sign-up asks for a card; the Owner will see.
- **Cost in Neurons** (the pricing page's units). A 1376 x 768 image is 1.06 MP, about 4 tiles of 512 x 512, or 6 if each side rounds
  up, so I give both:
  - FLUX.2 klein 4B (fixed 4 steps, up to 4 input images): 26.05 per output tile, 5.37 per input tile. Room-size text to image is
    about 105 to 156 Neurons, so **about 64 to 95 a day**. With one reference image (an edit, `extend`, a Look) about 127 to 188, so
    **about 53 to 79 a day**. With 4 references about 35 to 52 a day.
  - FLUX.2 klein 9B: $0.015 for the first megapixel (1,364 Neurons) plus 182 per input megapixel, so about 1,560 for one room-size
    edit: **about 6 a day**.
  - FLUX.1 schnell (text only): 4.8 per tile and 9.6 per step, about 57 to 67 at 4 steps: about 150 a day.
  - Lucid Origin and Phoenix (Leonardo's models): 636 and 530 per tile, so about 2,500 to 3,800 per room-size image: about 3 a day.
  - SDXL (image input with `strength`, 256 to 2048 px) and SD 1.5 inpainting (a `mask`): their Neuron prices are not in the pricing
    page's image table, so their quota use is unknown.
  - The Owner's need is about 11 generations a day on average (4,000 a year), with bursts of tens. klein 4B covers it with room to
    spare: a year's free allowance is 3.65 million Neurons, about 19,000 to 29,000 klein 4B room-size images.
- **API:** `POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/@cf/black-forest-labs/flux-2-klein-4b`, a bearer
  token, multipart form fields `prompt`, `input_image_0` to `input_image_3`, `width` and `height` (256 to 1920, default 1024 x 768),
  `guidance`, `seed`. A base64 image comes back. The room canvas of 1376 x 768 is in range. The text-to-image rate limit is 720
  requests a minute. klein has no mask, so a Look edit is an instruction in the prompt.
- **Terms:** the [data usage page](https://developers.cloudflare.com/workers-ai/platform/data-usage/): inputs and outputs are
  "Customer Content"; Cloudflare keeps none after the request (zero data retention), does not train on them, says "you own, and are
  responsible for" them, and does not show them to other customers. So a free output is not public. No watermark or content
  credential is mentioned on the pages read.
- **The licence question to settle first.** The model cards for klein 4B, klein 9B, schnell and FLUX.2 dev give BFL's
  [terms of service](https://bfl.ai/legal/terms-of-service) as their "Terms and License". Those terms (read in round 1) grant BFL a
  licence to train on inputs and outputs, with an opt-out by e-mail, and forbid intentionally removing AI content marking or
  transparency metadata. The models are Cloudflare-hosted with zero retention, so BFL should not see the data; but the licence text
  still points at BFL's terms. The Owner dropped FLUX for exactly that. My reading: the training clause is moot, the "do not remove
  marking" clause could still apply if outputs carry any, and I saw no marking. It is the Owner's call, and the rule is not to add a
  model whose commercial licence is not confirmed, so no FLUX model on Cloudflare enters Kiripix until the Owner says yes. The Lucid
  Origin and Phoenix cards link Leonardo's terms (403, unread); SDXL links the Stability licence (not read here).
- **Quality is unknown.** klein 4B is a 4B distilled model, not Nano Banana, and room Sources are the likeliest weakness. Step 3 is
  the test.

## Pollinations in detail

- [API reference](https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md): a secret key (`sk_`) from the dashboard;
  an account balance that is "Quest balance + paid balance", in US dollars; the README says "Add to your balance by contributing,
  without a credit card". Models are flagged `paid_only` in [its image list](https://gen.pollinations.ai/image/models); the ones
  flagged false include flux.2-klein-4b ($0.005 an image in the list), flux.1-schnell and flux.1-kontext-pro (an edit model).
- Not found: the size of the free balance, whether it renews daily, the terms of use. The reference says "Media URLs are public reads",
  so generated images sit on public URLs. The Owner would have to sign in to see the balance. It is worth the Owner's time only if
  Cloudflare fails and the balance covers about 10 images a day.

## What I could not read (round 2)

AI Studio's live rate-limit page; Cloudflare's sign-up (card or not) and the Neuron price of SDXL and the inpainting model; Leonardo's
and Ideogram's pricing and terms (403); PixelLab's plans; Pollinations' free balance and terms; Krea's free-plan commercial rights and
API price.

## Recommendation

Run a **reduced step 3 on Cloudflare Workers AI with FLUX.2 klein 4B, and nothing that costs money.** If it does not reach the
Owner's bar, close the trial with "keep using the AI Studio UI and the inbox ([0350](../0350-m6-source-inbox.md))".

1. **Cloudflare Workers AI**, the only candidate with a free daily quota usable through an API at room size and large enough for
   the volume.
   - The Owner needs: a Cloudflare account on the free plan (if it asks for a card, stop and say so); an API token with Workers AI
     permission; the account id; env vars `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` (the placeholders in Cloudflare's own
     examples; I found no mandated names). Also a yes or no on the BFL licence reading above.
   - The step 3 set runs on klein 4B (about 50 to 90 images a day available): a room Source with 4 Variants, one `extend` piece, one
     Look edit, one Prop state, one VFX strip, and an emotion if wanted. No sprite animation: it has no animation model, so animation
     stays on the 3D route and the inbox.
   - The bar: kept per generated image at least as good as the Owner's 1 in 10 in the UI, and the Kiripix scores (step 4) no worse.
     If room Sources fail but Look edits, Props and `extend` pass, the recommendation becomes Cloudflare for those and the UI for
     room Sources.
2. **Pollinations**, only if Cloudflare fails and the Owner finds a free balance worth about 10 images a day and accepts public
   output URLs.
3. **Everything else closes:** Gemini API, OpenAI, FLUX direct, Retro Diffusion (a taster), PixelLab, Krea, fal, Replicate, SpriteBrew.

### If the trial closes instead

The answer for every task is "keep using the AI Studio UI and the inbox". Implied follow-ups: nothing for `gen`; [0143](../0143-m6-gen-a-look-edit.md)
stays deferred with that said in its Why; spec §16 decision 5 closes as "no API Provider first; the UI and `inbox`", and §14's
"Generation and agents, deferred" stays. No tickets numbered 0365 or above are needed.

### If Cloudflare passes

Follow-up tickets, to be filed from 0365 upward after the step 3 results: a Cloudflare Provider adapter and `gen` (ml-engineer); a ledger
counted in Neurons per day, because the monthly dollar cap `budget_usd_month` does not fit a free daily quota (ml-engineer, depends on
the adapter); `gen` driving `extend` (core-engineer, depends on both); and 0143 updated to the chosen Provider.
