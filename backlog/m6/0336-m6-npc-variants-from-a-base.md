---
status: todo
milestone: M6
agent: none
type: spec
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0337-m6-cast-sheet-stacks-and-swaps.md]
---

# M6: background NPCs from a base, its Wearables and its colours, with no new render

Spec §6.3 (a character made from a base, Wearables), §9 (the Character and Wearable exports) and §14 (M6). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Builds on M4's bases
([0165](../m4/0165-m4-characters-share-a-base.md), ADR 0012) and M5's Wearables
([0152](../m5/0152-m5-character-layers.md), 0290 to 0295). The game's side is `../urban-mystery-club/docs/TECHNICAL.md`
("Player avatar", "Authored characters and NPCs") and its M17 (`docs/ROADMAP.md`).

## Problem Statement

The game's M17 needs Chapter 1's NPCs: the speaking cast and a crowd of background figures. Today an NPC is either a
character of its own (a Model, a render, about 10 minutes for a full body with 15 clips, an atlas of its own) or a PixelLab
sprite. A background NPC needs neither: a base body, a hair style and an outfit from the Wearables already rendered, and
colours from the swap shader. The game's `CharacterSprite` already stacks layers and swaps ramps for the MC, and its
`set_colours` works for "any NPC with ramps".

## The direction

A background NPC is a **choice, not a render**: a body (a base character), Wearables rendered on that body, a stacking
order, and a colour per Part (a ramp from the Project palette, as long as the Part's row in the ramp table). Nothing is
rendered for it. Kiripix checks the choice and shows it; the game draws it with what it has.

## Questions for the Owner, before the work tickets

| # | Question | Recommendation |
|---|---|---|
| Q1 | **Who holds an NPC's appearance?** (a) Kiripix: an Asset of a new Kind (say `npc`) with a `choose` Stage and `export`, which writes an appearance file the game's actor data names. (b) The game: its `data/actors/` hold the body, Wearables and colours, and Kiripix only previews and checks a list the game hands it. | **(a)**, because Kiripix already owns every check the choice needs (the Wearable fits the body, the stack, the ramps on the palette), the preview, and the Manifest's frozen IDs. The game reads one small file per NPC instead of growing its own appearance data. A new Kind needs an ADR, like 0012 for bases. |
| Q2 | **What may an NPC change?** Only Wearables and colours, or also the body's clips (fewer: an NPC with no battle clips) and `render` `height`? | Wearables and colours only. A different height or clip set is a character made from the base (0165), which renders. A background NPC plays the base's exploration clips. |
| Q3 | **Variants in bulk:** should Kiripix make N NPCs at once, by a seed, from allowed Wearables and colour lists (`kiripix new npc crowd --base character.body_f --count 12 --seed 3`)? | Yes, as a second step after one NPC works: the gate's crowd for a ch01 street is about a dozen figures, picked by hand they cost the Owner more than the rooms. The Owner rejects or re-rolls single ones. |
| Q4 | **Colours from where?** Any palette colours, or named colour sets per Part in the Project (the game's 3 skins × 3 hair colours)? | Named sets in the Project's ramp table (`[[character.ramps]]` gains `choices`), so an NPC names `hair=auburn` and the game's appearance data and Kiripix share one list. Needs a `schema_version` bump and a migration. |
| Q5 | **Do speaking NPCs use this too,** or stay characters of their own with portraits? | Background NPCs only in M6. Speaking cast stay characters (they need their own faces at 52 px and portraits). |

## What the work tickets will cover (written after the answers)

To the recommendations: an ADR for the Kind; the Kind and its Stages (core-engineer); its Checks: every Wearable's body is the
NPC's base, the stack check from 0294, every colour a choice of its Part (imaging-engineer); its export and Manifest entry
(godot-export); the bulk maker (core-engineer); the UI's NPC screen with the stacked preview (ui-engineer). The preview Op
itself comes first, in [0337](0337-m6-cast-sheet-stacks-and-swaps.md), so the Owner can answer Q2 to Q4 by looking at
stacked figures.

## Acceptance criteria

- [ ] The Owner's answers to Q1–Q5 recorded here, with the date.
- [ ] The work tickets written, with `agent:` and `depends_on`, and listed here.
- [ ] Spec §6.3 and §14 updated to the answers.

## Out of scope

- The game's `CharacterSprite`, its shader and its actor data format (unless Q1 is (b), where the game's list is its own).
- New renders for NPCs: never, by the direction.
