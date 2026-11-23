---
status: done
milestone: M6
agent: ml-engineer
type: ticket
depends_on: [0379-m6-openai-provider-and-gen.md]
---

# M6: `gen` states each call's cost and the month's remaining budget, and refuses a call past the cap before sending it

Spec §4 (`[providers] budget_usd_month`), §10 (`gen`, `cost`, "Spend"). Written on 2026-11-23, when the Owner set the art
repo's budget to $10 a month (`urban-mystery-club-art/kiripix.toml`, was $0 by DEC-004). Lands with the first `gen`,
[0379](0379-m6-openai-provider-and-gen.md): OpenAI's GPT Image, the Owner's choice ([0353](0353-m6-provider-research.md)).

## What to do

1. Before each Provider call, `gen` works out the call's **estimated cost** (the Provider's price for that size, quality
   and count, from a price table kept with the Provider, not guessed from the response) and the month's **remaining
   budget** (`budget_usd_month` less the ledger's spend for the calendar month, UTC). It shows both before sending: on the
   CLI a line on stderr (`gen: room.x, 4 images, est. $0.17; $6.42 of $10.00 left this month`), and in the JSON result's
   `data` (`estimated_usd`, `remaining_usd`, `budget_usd_month`).
2. A call whose estimate would take the month's spend over the cap is **refused before it is sent**: `cost.budget_exceeded`
   (exit 3, `owner_action`: raise `[providers] budget_usd_month` or wait for the month), with the estimate and the
   remaining budget in the message. Nothing is sent, nothing is recorded. `-n` larger than the budget allows is refused
   whole, not cut down.
3. Each sent call appends its actual cost (the Provider's reported usage where it gives one, else the estimate, marked so)
   to the cost ledger (`.kiripix/`, `.jsonl`, append-only). A failed call the Provider still bills is recorded too.
4. `budget_usd_month = 0` refuses every paid call (the `import` Provider costs nothing and is never refused).
5. `kiripix cost --month` shows the spend, the cap and what's left.

## Acceptance criteria

- [ ] CLI seam, with a test Provider whose price is fixed: the estimate and remaining budget are in the result and on
      stderr before the call; a call that would cross the cap exits 3 with `cost.budget_exceeded` and the ledger is
      unchanged; a call that fits exactly is sent.
- [ ] The spec's §10 "Spend" line names the pre-call estimate, the remaining budget and the refusal.

## Result

Built with [0379](0379-m6-openai-provider-and-gen.md), in `kiripix/core/gen.py` (`check_limits`, `notice_line`), on the
ledger in `kiripix/core/ledger.py`.

- Before each call, `gen` gives the estimate (the Provider's dated price table for that model, size, quality, count and
  input images, never the response) and the month's budget left (`budget_usd_month` less the ledger's spend in the calendar
  month, UTC). It prints them as a line on stderr (`gen: prop.bench, 2 images, est. $0.08; $10.00 of $10.00 left this
  month`), through a new `notice` progress event that the CLI prints as plain text even without `--progress`. They are in
  `data` too (`estimated_usd`, `remaining_usd`, `budget_usd_month`). `approve` shows them again with the ledger as it is then.
- A call whose estimate would take the month's spend over the cap is `cost.budget_exceeded` (exit 3, `owner_action`), with
  the estimate and what's left in the message. Nothing is sent, written or recorded (no pending call and no canvas either),
  and `-n` is refused whole. The sums are rounded to 6 places before the comparison, so a call that fits exactly is sent
  (tested). `budget_usd_month = 0` refuses every paid call. The `import` Provider paints nothing, so `gen` never sends to it.
- Each sent call appends its cost: the reported usage priced from the table, or the estimate, marked `estimated`. A refused
  call the Provider says it billed (`ProviderError.billed_usd`) is recorded with `outcome` `failed`. A call cancelled after it
  was sent is recorded at its estimate (`outcome` `cancelled`), because it may still be billed.
- `kiripix cost --month` shows the spend, the cap and what's left.
- The last limit check and the send run under one Project-wide lock (`providers`), in `gen` with `approve = "none"` and in
  `approve`, so two calls can't both pass the cap and then both be sent.
- Not done: reserving budget for pending calls. A pending call doesn't count against the cap until it is approved, and
  `approve` checks the budget again, so the cap still holds.
- Spec §10's "Spend" line names the estimate, the remaining budget, the refusal and the ledger.
