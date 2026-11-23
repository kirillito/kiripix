---
status: todo
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
