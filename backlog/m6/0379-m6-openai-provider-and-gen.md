---
status: todo
milestone: M6
agent: ml-engineer
type: ticket
depends_on: [0353-m6-provider-research.md]
---

# M6: the OpenAI Provider, `gen`, the cost ledger and `cost`

Spec §4 (`[providers]`), §10 (`gen`, `cost`, "Spend"), §14 (the image API Provider), §16 decision 5. The Owner chose OpenAI's
GPT Image on 2026-11-23 ([0353](0353-m6-provider-research.md)'s Result). The first Command that calls a Provider.

## What to build

1. **The OpenAI Provider** in `kiripix/providers/`: image generation, and editing with input images (a canvas, a Source, a
   reference), through the OpenAI API. The key comes from `OPENAI_API_KEY` (environment or the git-ignored `.env`), never
   from `kiripix.toml`, a log, a finding or a test. The model, size and quality are read from the Owner's choice in
   `kiripix.toml` (`[providers.openai]`: a new section, so `schema_version` goes up with its migration), with defaults
   stated in the ticket's Result and read from OpenAI's model page on the day.
2. **`kiripix gen <id> [-n N] [--provider openai]`** for a room's Source (from the brief's built prompt, [0348](0348-m6-brief-renders-the-prompt.md)),
   a Prop and its states, and a portrait's emotions (the Owner: portraits are in). Each result is stored as a Variant, the way
   `import` stores one; `gen` never picks. Logged in `history.jsonl`. Long calls take the cancel token (ticket 0031).
3. **The cost ledger** (`.kiripix/`, `.jsonl`, append-only): one line per call sent, with the Provider, model, size,
   quality, count, the cost (OpenAI's reported usage priced from a table kept with the Provider, with the table's date) and
   the Asset.
4. **`kiripix cost [--month]`**: spend from the ledger by month and by Provider.
5. The cost estimate before each call and the cap are [0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md), on
   this ledger; build them together if that's simpler, and say so in the Result.

## Acceptance criteria

- [ ] CLI seam with a fake Provider (no network in tests): `gen -n 2` adds 2 Variants, logs them, writes 2 ledger lines,
      and changes nothing else; `cost --month` sums them. A new Command's sample is in `tests/cli/test_contract.py`.
- [ ] No key in any file the tests or the Command write; a missing key is a finding with an `owner_action`.
- [ ] One real call on the art Project's copy (the Owner's key, the Owner's yes first), its cost recorded in the Result.
