---
status: todo
milestone: M5
agent: ml-engineer
type: ticket
parent: ../m4/0127-m4-room-looks.md
---

# M5: `gen --look`: make a Look's edit through a Provider

Spec §6.1 (Looks), §10.5 and §14 M5. Needs M5's first Provider with image editing, and [0129](../m4/0129-m4-look-variants.md). Moved from M4 on 2026-11-08, when M4 became rooms for grid battles.

## What to build

- `kiripix gen <id> --look <look> [-n N]` sends the room's Source with an edit prompt to a Provider that can edit
  images, and stores each result as an edit Variant of that Look, the same way `import --look` does.
- The prompt comes from a template per Kind (`style/prompts/`), starting from Lost-and-Found's wording: "Edit this image.
  Keep everything exactly the same except: …", with the Owner's words after it.
- Logged in `history.jsonl` and the cost ledger, and within the budget, as every `gen` call is.

## Acceptance criteria

- [ ] With a fake Provider: `gen --look` adds N Variants under `src/looks/<look>/`, logs them, and touches nothing else.
- [ ] Over budget, it refuses before calling.
