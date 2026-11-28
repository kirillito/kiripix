---
status: done
milestone: M6
agent: reviewer
type: adr
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0336-m6-npc-variants-from-a-base.md]
---

# M6: ADR: a background NPC is an Asset of Kind `npc`, a choice and not a render

Spec §3 (Kinds), §6.3 (a character made from a base, Wearables), §9 and §14 (M6). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), from the Owner's answers to [0336](0336-m6-npc-variants-from-a-base.md)
(2026-11-20: Q1 (a), Q2 Wearables and colours only, Q3 bulk after one works, Q4 named colour sets, Q5 background only).
Draft the ADR and the spec change; the work tickets are [0356](0356-m6-npc-kind-and-choose-stage.md) to
[0360](../m7/0360-m7-ui-npc-screen.md).

## What the ADR settles

- **A new Kind, `npc`,** beside ADR 0012's bases: an Asset that names a base character (`base`), Wearables rendered on that
  base, a stacking order, and one named colour choice per Part. Nothing is rendered for it; its Stages read the base's and
  the Wearables' built outputs. Why not (b), the game's actor data: the checks, the preview and the Manifest's frozen IDs
  are Kiripix's already.
- **The recipe:** proposed **choose → export**. `choose` holds the choice (Decisions, or parameters: say which, and why) and
  writes `npc.json`; its input hash covers the base's and the Wearables' `sheet` and `palette` outputs, so a re-render of the
  base makes every NPC on it stale. `export` writes one appearance file per NPC.
- **What an NPC may change** (Q2): Wearables and colours only. Never the body's clips, `height` or camera. A different height or
  clip set is a character made from the base (0165), which renders.
- **Colours** (Q4): `[[character.ramps]]` gains `choices`, named ramps (`auburn = [...]`) as long as the Part's row; an NPC
  names `hair = "auburn"`. Shared with the game's appearance data, so one list holds.
- **Speaking cast** (Q5) stay characters of their own, with portraits.
- **Bulk** (Q3): `new npc <prefix> --base … --count N --seed S` makes N Assets, each an ordinary `npc` the Owner can change or
  delete; the seed picks from allowed Wearables and choices. Say where "allowed" lives (a list on the base, or the command's
  flags).
- Alternatives considered and why they lost: (b) the game's data; an NPC as a `character` with a `from_base` flag; a
  `variants` list inside one Asset (one ID for a crowd, so the Manifest can't freeze each figure).

## Acceptance criteria

- [x] `docs/adr/0015-…` drafted, with the alternatives.
- [x] Spec §3's Kinds, §6.3 (an NPC paragraph) and §9 (an NPC row) updated, marked "proposed" until the Owner accepts.
- [x] GLOSSARY.md gains **NPC** (the Kind) if the ADR keeps the word.
- [x] The Owner's acceptance recorded here, with the date.

## Result

- **Accepted by the Owner, 2026-11-20.** The ADR was then written from the accepted direction (main session):
  [docs/adr/0015-a-background-npc-is-a-choice-not-a-render.md](../../docs/adr/0015-a-background-npc-is-a-choice-not-a-render.md).
- The two points left open above are settled there: the choice is **parameters** of `choose` (`wearables`, `colours`), not
  Decisions (a few names with nothing drawn on a grid; the bulk maker sets them as a person does); and what a crowd may pick
  from is given by the bulk command's **flags** (`--wearables`, `--choices`; default everything on the base), with nothing new
  stored on the base.
- Spec §3 lists the `npc` Kind, §6.3's NPC paragraph is no longer "proposed", §9 has an NPC row. GLOSSARY.md has **NPC**.

