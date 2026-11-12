---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0161-m4-characters-after-the-m3-gate.md
depends_on: [0156-m4-edit-a-clip.md]
---

# M4: copy a character's clips to another character (stop-gap before 0165)

Spec §6.3 (clips). Added 2026-11-12 for the game's M03. **Chosen by the Owner on 2026-11-12** over pulling part of
[0165](../m5/0165-m5-characters-share-a-base.md) forward (see the question below).

## The gap

The game's M03 has four character Assets: 2 bodies x 2 outfits (DEC-052). Each one decides its clips on its own: idle, walk and
run, plus one attack per class at M03 (6 clips), and full battle sets later (attack, skill, hit and so on for 3 classes, about
15 to 18 clips). That's 24 `clip` Decisions at M03 and 60 to 70 later, each the same name, source and range on every Asset, and
each clip-source file imported four times. A range changed on one (0156) must be changed on the others by hand.

Two other costs are outside this ticket:
- **The rig.** Each Asset needs a rigged file. A second outfit modelled on the first outfit's rigged `.blend` (same armature) is
  validated by `rig` with no Mixamo trip, so the 4 trips can be 2. Worth telling the Owner before the second outfit is made.
- **Renders** stay per Asset: four bodies are four renders (DEC-052 accepts ~40 min).

Characters made from a **base** (0165, M5) fix all of it, but they need cross-Asset inputs, an ADR, and the base Models trial
([0164](../m5/0164-m5-claude-built-base-models-trial.md)) first.

## What to build

- **`kiripix clips copy <character> --from <other>`** (a writing Command): for each of `<other>`'s current `clip`
  Decisions, records the same Decision on `<character>`, in the journal like any other, so `undo` takes them back one by one.
  With `--clip idle,walk` only those.
- The clip-source files those Decisions name are imported into `<character>` too (the same bytes, so the same hashed name; the
  art repo's LFS stores them once). A clip whose source is an action of `<other>`'s rigged file is copied as it is; if
  `<character>`'s rig has no such action, `clips` fails with its own `clips.source_missing`.
- A clip `<character>` already has is skipped with a warning naming it, unless `--replace`, which decides it again (0156: a
  replacement keeps its name).
- Both Assets must be characters; `<other>` is only read. `--dry-run` lists the Decisions and files it would add.
- There is no link: a later change on `<other>` isn't carried over. Run it again with `--replace`.
- `describe` and a sample in `tests/cli/test_contract.py`.

## Acceptance criteria

- [x] CLI seam, on the fake: copying from a character with three clips and one clip-source file gives the second the same
      `clips.json` (bar `source_hash` paths), and `undo` three times removes them.
- [x] An existing clip is skipped with a warning; with `--replace` it takes the other's range.
- [x] Copying from a room fails with a finding naming the Kind.

Budget: 100–180k tokens.

## Question for the Owner

This stop-gap (about 1 ticket), or part of 0165 now: a character names a base and uses its rigged file, clip sources and clip
Decisions (needs cross-Asset Stage inputs and an ADR; 3 to 5 tickets, and 0165's design is meant to follow the M5 trials)?
Recommendation: this stop-gap, plus the second outfit modelled on the first's rigged file.

**Answered 2026-11-12: this stop-gap**, and the second outfit of each body is modelled on the first outfit's rigged file, so it
needs no Mixamo trip of its own.
