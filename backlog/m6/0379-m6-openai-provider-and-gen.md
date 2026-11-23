---
status: done
milestone: M6
agent: ml-engineer
type: ticket
depends_on: [0353-m6-provider-research.md, 0348-m6-brief-renders-the-prompt.md]
---

# M6: the OpenAI Provider, `gen`, the cost ledger and `cost`

Spec §4 (`[providers]`), §10 (`gen`, `cost`, "Spend"), §14 (the image API Provider), §16 decision 5. The Owner chose OpenAI's
GPT Image on 2026-11-23 ([0353](0353-m6-provider-research.md)'s Result). The first Command that calls a Provider.

## What to build

1. **The OpenAI Provider** in `kiripix/providers/`: image generation, and editing with input images (a canvas, a Source, a
   reference), through the OpenAI API. The key is `OPENAI_API_KEY` in the art Project's git-ignored `.env`, read from the
   Project's root only; the Kiripix repo, its tests and CI have none (the Owner, 2026-11-23). Never in `kiripix.toml`, a
   log or a finding. The model, size and quality are read from the Owner's choice in
   `kiripix.toml` (`[providers.openai]`: a new section, so `schema_version` goes up with its migration), with defaults
   stated in the ticket's Result and read from OpenAI's model page on the day.
2. **`kiripix gen <id> [-n N] [--provider openai]`** for a room's Source (from the brief's built prompt, [0348](0348-m6-brief-renders-the-prompt.md)),
   a Prop and its states, and a portrait's emotions (the Owner: portraits are in). Each result is stored as a Variant, the way
   `import` stores one; `gen` never picks. Logged in `history.jsonl`. Long calls take the cancel token (ticket 0031).
3. **The cost ledger** (`.kiripix/`, `.jsonl`, append-only): one line per call sent, with the Provider, model, size,
   quality, count, the cost (OpenAI's reported usage priced from a table kept with the Provider, with the table's date) and
   the Asset.
4. **`kiripix cost [--month]`**: spend from the ledger by month and by Provider.
5. **Tests cost $0** (the Owner, 2026-11-23): no test calls OpenAI. Tests use a fake Provider (fixed images, fixed price)
   from the test recipes module, loaded the way `KIRIPIX_TEST_RECIPES` loads the test Kind, never in `kiripix/`. The OpenAI
   Provider's own request code is not tested. The pytest and Playwright harnesses drop `OPENAI_API_KEY` from the
   environment they give `kiripix`, so a key in the shell can't reach a test.
6. The Owner approves each call ([0381](0381-m6-the-owner-approves-each-provider-call.md)): until that lands, `gen` with a
   paid Provider is not used on the art Project.
7. The cost estimate before each call and the cap are [0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md), on
   this ledger; build them together if that's simpler, and say so in the Result.

## Acceptance criteria

- [ ] CLI seam with a fake Provider (no network in tests): `gen -n 2` adds 2 Variants, logs them, writes 2 ledger lines,
      and changes nothing else; `cost --month` sums them. A new Command's sample is in `tests/cli/test_contract.py`.
- [ ] No key in any file the tests or the Command write; a missing key is a finding with an `owner_action`.
- [ ] Both harnesses drop `OPENAI_API_KEY`; no test, in `tests/` or `web/e2e/`, uses the OpenAI Provider.

## Result

Built together with [0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md) (the estimate and the cap) and
[0381](0381-m6-the-owner-approves-each-provider-call.md) (pending calls), since all three sit on the same plan of a call. The
logic is one core module, `kiripix/core/gen.py`, and the Commands are in `kiripix/commands/gen.py`.

- **The Provider interface** (`kiripix/providers/base.py`): a prompt, a model, a size, a quality, a count and optional input
  images in; PNG bytes and the cost out. Each Provider keeps its own dated price table (`estimate_usd`) and says which sizes
  its model takes (`fit_size`). It never reads a key: core reads the Project's `.env` and passes it in. Providers register
  as Runners do (`register_provider`), and the test harness adds its fake ones through `KIRIPIX_TEST_RECIPES`.
- **The OpenAI Provider** (`kiripix/providers/openai.py`): `POST /v1/images/generations` (JSON) and `/v1/images/edits`
  (multipart, one `image[]` part per input image), on the standard library's `urllib`, so no new dependency. The call runs on
  a thread and the cancel token is checked every 0.2 s (ticket 0031). Edits are sent as JSON since the follow-up in
  [0380](0380-m6-gen-drives-extend.md) (the mask, `input_fidelity`, the size sent), whose tests run this request code over a
  fake HTTP layer, at the Owner's request; no test reaches the network.
- **Defaults, read on 2026-11-23** from developers.openai.com (the image generation guide, the pricing page, the models
  catalogue, the deprecations page, the Images API reference): model **`gpt-image-2.6-sunburst`** (what OpenAI tells new
  integrations to use, and the edit endpoint's default; `gpt-image-2` is deprecated with shutdown on 2027-02-10, and
  `gpt-image-1` was shut down on 2026-10-23), quality **`medium`**, size **empty**: the image the call is for (a room's
  brief canvas, 1376 x 768; the `extend` canvas; the edited image; 1024 x 1024 for a Prop or a portrait), fitted to the
  model's rules (edges multiples of 16, aspect 1:3 to 3:1, 655,360 to 8,294,400 px).
- **The price table** (dated 2026-11-23): OpenAI publishes only token rates for these models (image output $30, image input
  $8, text input $5 per million), and its per-image calculator wasn't readable. So the estimate takes the output tokens per
  image from `gpt-image-2`'s last per-image table at 1024 x 1024 (200 low, 1,767 medium, 7,033 high), scaled by the image's
  area, plus the prompt's tokens and about 1,000 tokens per input image. A 1376 x 768 medium image is estimated at about
  $0.054. The ledger's `usd` is the reported `usage` priced at the same rates. Once a few real calls are in the ledger,
  compare the estimates with the actual costs, and correct `OUTPUT_TOKENS_PER_MEGAPIXEL` if they drift.
- **The key:** `OPENAI_API_KEY` in the `.env` at the Project's root, read from there only, never from the environment. A
  missing key is `provider.key_missing` (exit 3, `owner_action`). A Provider's error message has the key masked before it
  reaches history or a finding. Both harnesses drop `OPENAI_API_KEY`: `tests/conftest.py`, and `web/e2e/harness.ts` for every
  environment it gives `kiripix`, not only the fake-Runner one.
- **`kiripix gen <id> [-n N] [--provider p] [--prompt "..."] [--look l | --state s | --emotion e | --side east] [--reference png]`**:
  a room's Source from its brief's built `prompt.txt` (`gen.no_prompt` without one), a Prop's or a portrait's Source from
  `--prompt` (`gen.prompt_needed` without), and edits of the picked Source for a Look, a state or an emotion
  ([0143](0143-m6-gen-a-look-edit.md)). `--reference` sends more images, such as the projection reference the room-brief skill
  attaches. Each image is stored by the same functions `import` uses (`imported.jsonl` names it `gen-<call>-<n>.png`); `gen`
  never picks. Each call is logged in `history.jsonl` with the Stage it feeds (`source`, `looks`, `extend`), `provider`,
  `provider_model` (spec §5's names), size, quality, count, call ID, the full prompt, the input images' paths and SHA-256,
  the cost and the Variants. So the committed history keeps what made each Variant. That is ADR 0002's key in part: the
  results are committed as Variants, but nothing replays a Provider call from it. `[providers] default = "import"` is `provider.not_generating`.
- **The cost ledger:** `.kiripix/cost.jsonl`, append-only, `schema_version` 1. **One line per call sent, not per image:** a
  call with `-n 2` is one request and one bill, so it is one line with `count` 2 and `images` 2. That differs from the first
  acceptance item's "2 ledger lines"; the line keeps the per-image count, and `cost` sums images too.
- **`kiripix cost [--month] [--since <time>]`** (a Probe): spend by month and by Provider, calls and images, this month's
  spend, the cap and what's left, and how many lines are estimates. `--since` sums the calls, cost and reported tokens since
  a time, such as the start of an agent's session (the Owner, 2026-11-23).
- **What a call actually cost** (the Owner, 2026-11-23): OpenAI's response reports token counts (`usage`: input tokens, split
  into text and image, and output tokens), not dollars. The ledger line and the history line keep those counts (`usage`),
  `usd` is them priced at the table's rates, and after each call `gen` and `approve` print a line on stderr: `gen: room.x,
  call <id> cost $0.0512 (from the reported usage; tokens 1,104 input, 1,632 output); $0.17 of $10.00 spent this month`.
  The same figures are in `data` (`usd`, `usage`, `month_spent_usd`), so an agent's session can keep a running total from the
  results, or ask `cost --since`.
- **Settings:** `[providers]` gains `approve`, `max_images_per_call`, `max_calls_per_day` (0381) and `[providers.openai]`
  (`model`, `quality`, `size`). Project `schema_version` goes from 13 to 14, one bump for both tickets, with its no-op
  migration (the defaults are read). `init` writes the new keys and a commented `[providers.openai]`.
- No Stage changed, so no `StageSpec.version` bump.
- Spec: §4 (`[providers]`, `[providers.openai]`, secrets, the `<kind>-edit` and `room-extend` templates), §10 (`gen`,
  `approve`, `reject`, `cost`, "Spend"), §10.3 (`approve` is owner-only), §13 (`providers/`).
- Tests: `tests/cli/test_gen.py` (18 tests), on two fake Providers in `tests/fixtures/kiripix_test_recipes.py` (`fake`: $0.04
  an image, no key; `fake_keyed`: needs `FAKE_PROVIDER_KEY`). Contract samples for `gen`, `approve`, `reject` and `cost` are in
  `test_contract.py`, and their REST bodies in `test_serve.py`. No test names the OpenAI Provider.
