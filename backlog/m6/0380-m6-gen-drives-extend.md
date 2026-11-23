---
status: todo
milestone: M6
agent: ml-engineer
type: ticket
depends_on: [0379-m6-openai-provider-and-gen.md, 0377-m6-extend-joins-a-re-rendered-strip.md, 0381-m6-the-owner-approves-each-provider-call.md]
---

# M6: `gen` drives `extend`: canvas, OpenAI, `add`

Spec §14 (the Owner's aim for `extend`, 2026-11-16), §16 decision 5. The Provider is OpenAI's GPT Image
([0379](0379-m6-openai-provider-and-gen.md)).

## What to build

- `kiripix gen <id> --side <side> [-n N]` writes the next canvas (`extend <id> canvas`), sends it with the room's prompt to
  the Provider as an edit, and keeps the N results as candidate pieces for the Owner, without joining any.
- The Owner (or the UI) joins the chosen one with `extend add`. GPT Image re-renders the kept strip, so a piece from it joins
  under `--max-residual 1` ([0377](0377-m6-extend-joins-a-re-rendered-strip.md)) with `extend.strip_repainted`; decide
  whether `gen` records which Provider made a piece so `add` raises the limit itself, and say why in the Result.
- Within the budget and its estimate ([0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md)).

## Acceptance criteria

- [ ] CLI seam with a fake Provider that returns a re-rendered strip (0377's synthetic piece): `gen --side east -n 2` keeps
      2 pieces, records no join, and `extend add` on one joins it.
- [ ] One real 2-screen room on the art Project's copy, with the cost and the Owner's minutes in the Result, beside
      [0134](../m4/0134-m4-trial-room-extended-both-ways.md)'s 25 minutes of hand work for four pieces.

## Result

The first acceptance item is built. The trial on a real room stays open, so `status` stays `todo`.

- `kiripix gen <room> --side <side> [-n N] [--prompt "<what the new area holds>"]` plans the next canvas at the default keep
  (`extend.plan_canvas`), sends it as an edit with the prompt, and keeps the N results as **candidate pieces** in
  `extend/candidates/<piece>.png`. Each has a `<piece>.json` beside it: the call, the Provider, the model, the sides, and
  whether the Provider re-renders the kept strip. `gen` joins nothing: `data.candidates` gives each file and its
  `kiripix extend <room> add <file>`.
- The canvas is written to `extend/canvas.png` only once the call has passed its limits. With `approve = "each"`, that is
  when the pending call is written, and `approve` refuses the call if the canvas changed since (`provider.call_stale`).
- The prompt is `style/prompts/room-extend.<ext>` if the Project has one (fields `prompt`, the room's built prompt, `sides`,
  `edit`, `bible`). Otherwise it is a head saying that the strip at the canvas's edge is the finished painting to continue
  toward the side, then the room's prompt, then "The new area holds: <words>". This keeps the room-brief skill's rule that
  every extension prompt restates the whole room prompt.
- **`gen` records which Provider made a piece, and `add` raises the limit itself.** Without `--max-residual`, `extend add` of
  a candidate whose record says its Provider re-renders the kept strip (GPT Image, and the fake Provider) joins under
  1.0 px (`RESIDUAL_CEILING`), with `extend.strip_repainted` when it registers above 0.5. Why: every GPT Image piece needs
  the raised limit (0377), and an Owner or a UI joining the chosen piece shouldn't have to know that. A piece from anywhere
  else (the inbox, a hand-made one) keeps `[extend] max_residual`, so a strip from another scene still fails. An explicit
  `--max-residual` always wins.
- Calls are held to the budget, its estimate and the approval, like every `gen` call.
- Tests: `test_gen_side_keeps_candidate_pieces_and_extend_add_joins_one_under_the_raised_limit`. The fake Provider returns
  the canvas re-rendered the way 0377's synthetic piece is (a sub-pixel wave, a per-channel gain, new noise): 2 candidates,
  no journal, and `extend add` on one joins without `--max-residual`. Also `test_the_extend_prompt_says_what_the_canvas_is`.

### Follow-up: keep the input image (feedback from the art repo, 2026-11-23)

The laneway's piece 3 through `gen --side south` (gpt-image-2.6-sunburst, medium, 1680 x 944) kept its 312 px strip on 1 of 3
tries; the other two re-composed or scaled it. `OpenAI.call` sent the canvas as a plain `image[]`, with no mask and no
fidelity, at a size `fit_size` had changed.

- **What the docs say** (developers.openai.com, read 2026-11-23: the Images API reference, the guide, the 2.6 Sunburst model
  page, pricing). A mask must have "the same format and size" as the first image and "an alpha channel". "Masking with GPT
  Image is entirely prompt-based", and the model "may not follow its exact shape with complete precision": a mask helps but
  pins nothing. The meaning of alpha isn't stated now; Kiripix sends GPT Image's earlier convention (alpha 0 = paint).
  `input_fidelity` is documented only for `gpt-image-1.5` (high, low) and `gpt-image-1-mini` (low); "for `gpt-image-2`, omit
  this parameter"; nothing is said for 2.5 or 2.6, nor what it costs. `markup` (2.5, 2.6) can't be combined with a mask. No
  parameter that pins or preserves the input exists. One more lever, not built: `complexity` (low, medium, high; default high
  on Sunburst and Flare), which the guide says "can introduce unwanted changes" when high and suits "focused edits" when low.
- **Edits are sent as JSON** (`images[].image_url` and `mask.image_url` as base64 data URLs), the body the reference documents
  for every field; the multipart form's mask field isn't documented anywhere.
- **The size sent:** the edited image (an `extend` canvas, a Look's, state's or emotion's Source) is placed top-left into the
  size `fit_size` gives, at scale 1 when it fits and shrunk to fit when it doesn't, its right and bottom edges repeated into
  the rest. Each result is brought to the size sent if the model answers another, cropped to where the image was placed, and
  scaled back. A 1678 x 937 canvas sent as 1680 x 944 comes back as 1678 x 937, pixel for pixel, with no stretch for
  registration to fight.
- **The mask** (an `extend` canvas): a PNG at the size sent, alpha 0 over the canvas's fill and over the padding, 255 over the
  kept strips, both strips (the L) for a corner. It is built from the canvas's own pixels and its fill colour (no strip pixel
  can be the fill: `contrasting_fill` keeps it 0.15 OKLab away), so it is exactly what the canvas shows. The pending call keeps
  the fill and the mask's SHA-256, and `approve` refuses a call whose mask would differ (`provider.call_stale`).
- **`[providers.openai] input_fidelity`:** `auto` (the default) sends `high` for an `extend` piece and a Look's edit when the
  model is one the docs name for it, and leaves it out otherwise, so with gpt-image-2.6-sunburst it is **not sent today**;
  `high` or `low` force it on every edit (to try 2.6: a refused call isn't billed), `off` never sends it. The estimate is
  unchanged: the docs give no price for it, and the reported usage gives the real cost.
- Recorded as the other parameters are: the mask's hash and the fidelity in the pending call, the history line and the ledger
  line. (Provider calls have no pinned-result key, ADR 0002; the history line is their committed record.)
- **Tests** (`tests/cli/test_gen.py`) run the OpenAI Provider's own request code over a fake HTTP layer, at the Owner's request
  (in the test recipes: `openai.set_transport`, never the network; no key but a fake one in the test's `.env`): the body
  carries the mask at the size sent, alpha 0 over the fill and the padding and 255 over the strip; a corner's mask is the L;
  `input_fidelity` is sent when forced or when the model takes it, and not for 2.6; a Look's edit comes back at the Source's
  size; a 4000 px canvas is shrunk into the model's limit with its mask and scaled back.
- **Not known yet:** whether the mask makes 2.6 keep the strip more often than 1 in 3. The next pieces' residuals will say.

### Still open, needs the Owner

- One real 2-screen room on the art Project's copy, with the cost and the Owner's minutes, beside 0134's 25 minutes for four
  pieces. It needs the key in the art Project's `.env`, a room template ([0348](0348-m6-brief-renders-the-prompt.md)'s draft),
  and the Owner's approval of each call.
