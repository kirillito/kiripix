---
status: done
milestone: M6
agent: ml-engineer
type: ticket
depends_on: [0379-m6-openai-provider-and-gen.md, 0381-m6-the-owner-approves-each-provider-call.md]
---

# M6: `gen --look`: make a Look's edit through a Provider

Spec §6.1 (Looks), §10.5 and §14 M6. Needs the OpenAI Provider ([0379](0379-m6-openai-provider-and-gen.md); GPT Image, the Owner's choice of 2026-11-23), and [0129](../m4/0129-m4-look-variants.md). Moved from M4 on 2026-11-08, when M4 became rooms for grid battles.

## What to build

- `kiripix gen <id> --look <look> [-n N]` sends the room's Source with an edit prompt to a Provider that can edit
  images, and stores each result as an edit Variant of that Look, the same way `import --look` does.
- The prompt comes from a template per Kind (`style/prompts/`), starting from Lost-and-Found's wording: "Edit this image.
  Keep everything exactly the same except: …", with the Owner's words after it.
- Logged in `history.jsonl` and the cost ledger, and within the budget, as every `gen` call is.

## Acceptance criteria

- [ ] With a fake Provider: `gen --look` adds N Variants under `src/looks/<look>/`, logs them, and touches nothing else.
- [ ] Over budget, it refuses before calling.

## Result

Built with [0379](0379-m6-openai-provider-and-gen.md). `kiripix gen <room> --look <look> [-n N] --prompt "<what changes>"`
sends the room's picked Source with the edit prompt, and stores each result under `src/looks/<look>/` with
`sources.import_look`, the function `import --look` uses.

- The prompt is `style/prompts/room-edit.<ext>`, rendered with the Owner's words as `edit` (and `look`, `asset`, `bible`).
  With no template, it is Lost-and-Found's wording: "Edit this image. Keep everything exactly the same except: <words>".
- The same path makes a Prop's state (`--state`, `import_state`) and a portrait's emotion (`--emotion`, `import_emotion`).
  Each is refused before the call when the state or emotion isn't declared.
- The size asked for is the Source's own, fitted to the model's rules; the Source is placed into that size and each result
  mapped back to the Source's size, and `input_fidelity` is `high` where the model takes it (the follow-up in
  [0380](0380-m6-gen-drives-extend.md)).
- Each call is logged in `history.jsonl` (`stage` `looks`, `look`) and the ledger, and is held to the budget and the
  approval like every `gen` call.
- Tests: `test_gen_look_adds_n_edit_variants_of_the_look_and_touches_nothing_else` (2 Variants under `src/looks/night/`,
  nothing else added, the same file `import --look` would store) and `test_the_edit_prompt_is_the_default_wording_or_the_kinds_template`.
  The budget tests in `test_gen.py` cover every `gen` call the same way.
