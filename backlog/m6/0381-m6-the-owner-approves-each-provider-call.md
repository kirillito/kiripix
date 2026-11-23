---
status: done
milestone: M6
agent: core-engineer
type: ticket
depends_on: [0379-m6-openai-provider-and-gen.md, 0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md]
---

# M6: the Owner approves each Provider call; an agent's `gen` only asks

Spec §10 ("Spend", owner-only Commands, §10.3), §4 (`[providers]`). The Owner, 2026-11-23: generation through OpenAI is
semi-automatic. Claude writes the prompts and runs `gen` from the game repo; the Owner watches the results and the number of
calls, and may approve each call. The owner-only guard (`kiripix/commands/calling.py`: an interactive terminal or the UI's
session) is a guardrail against an agent spending on its own, not security, and that is enough here.

## What to build

1. **`[providers] approve`**: `"each"` (the default) or `"none"`. A new key, so `schema_version` goes up with its migration.
2. With `"each"`, `gen` sends nothing. It writes a **pending call** to `.kiripix/calls/<id>.json` (atomic): the Asset, the
   Provider, model, size, quality and count, the full prompt, the input images (paths and hashes), the estimate and the
   month's remaining budget ([0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md)). It exits 3 with
   `provider.approval_needed`, the pending call in `data`, and `owner_action`: `kiripix approve <id>`.
3. **`kiripix approve <id>`**, owner-only: shows the pending call again, checks the budget again (the month may have moved),
   sends it, stores the Variants and the ledger lines as `gen` would, and deletes the pending call. Refused if an input
   image changed since it was written (`provider.call_stale`, fix: run `gen` again). `kiripix approve --list` and
   `kiripix reject <id>` (not owner-only: rejecting costs nothing).
4. In a Claude Code session the agent shows the Owner the prompt and the estimate from the result; the Owner approves in their
   own terminal or in the UI. A UI panel for pending calls and the month's spend is a follow-up for `ui-engineer`, filed
   from this ticket's Result if the Owner wants it.
5. **Limits besides the budget**, under `[providers]`: `max_images_per_call` (default 4) and `max_calls_per_day` (default
   20; counted from the ledger), each refused before a pending call is written.

## Acceptance criteria

- [ ] CLI seam with the fake Provider: `gen` writes a pending call, exits 3, writes no Variant or ledger line; `approve`
      without `KIRIPIX_TEST_OWNER` is `owner.required`; with it, sends once, and a second `approve` of the same id fails;
      `reject` deletes it; a changed input is `provider.call_stale`; `approve = "none"` sends from `gen` directly.
- [ ] The new Commands have samples in `tests/cli/test_contract.py`; spec §10 lists them; the glossary gets "pending call"
      if the reviewer agrees it is a domain word.

## Result

Built with [0379](0379-m6-openai-provider-and-gen.md) and [0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md).

- `[providers] approve = "each"` (the default) or `"none"`, plus `max_images_per_call` (4) and `max_calls_per_day` (20, UTC,
  from the ledger): Project `schema_version` 14, the same bump as 0379's `[providers.openai]`.
- With `"each"`, `gen` writes a pending call to `.kiripix/calls/<id>.json` (atomic; the ID is a ULID): the Asset, what it is
  for, the Provider, model, size, quality, count, the full prompt, the input images with their paths and SHA-256, the
  estimate, the month's budget left, and `again`, the `gen` command that plans it again. It exits 3 with
  `provider.approval_needed`, the pending call in `data.pending` and `owner_action` `kiripix approve <id>  (or kiripix reject
  <id>)`. No Variant, ledger line or history line is written. With `--side`, the canvas is written at this point (after the
  limits passed), so the Owner can look at it.
- **`kiripix approve <id>`** (owner-only, the same guard as `accept`): under the `providers` lock, checks the limits and the budget again, prints the
  estimate line, refuses the call when an input image changed (`provider.call_stale`, fix: the `gen` command again), sends
  it, stores the Variants, the ledger line and the history line as `gen` would, and deletes the pending call. A second
  `approve` of the same ID is `provider.call_unknown`. A call the Provider refuses stays pending, so the Owner can `reject`
  it or try again. `approve --list` lists the pending calls. It is owner-only like the rest of `approve`; an agent has each
  call's ID from `gen`'s result.
- **`kiripix reject <id>`** deletes a pending call; it is not owner-only.
- The two limits are refused before a pending call is written: `provider.too_many_images` (fix: `-n` at the limit) and
  `provider.daily_limit` (exit 3, `owner_action`).
- Spec §10 lists `approve` and `reject`, §10.3 names `approve` as owner-only, and §4 has the keys.
- **Not done, for the Owner:** "pending call" in the glossary. The ticket makes it the reviewer's call, and no review was
  asked for. The UI panel for pending calls and the month's spend isn't filed; file it for `ui-engineer` if you want it.
