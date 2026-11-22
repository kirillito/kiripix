# A background NPC is an Asset of Kind `npc`: a choice, not a render

**Status: accepted** (2026-11-20, by the Owner, for ticket 0355, from the answers to 0336).

The game's chapter 1 needs a crowd of background figures beside its speaking cast. Today an NPC is either a character of its
own (a Model, a render of about 10 minutes for a full body with 15 clips, an atlas of its own) or a PixelLab sprite. A
background figure needs neither: a base body (ADR 0012), a hair style and an outfit from the Wearables already rendered on
that body (M5, tickets 0290 to 0295), and colours from the swap the game already does (`CharacterSprite.set_colours`). The
stacked, swapped preview exists since ticket 0337 (`cast-sheet`).

We considered four ways:

1. **The game holds it**: its `data/actors/` name the body, the Wearables and the colours, and Kiripix only previews and checks a
   list the game hands it. The checks, the preview and the frozen IDs would be split between two repos, and the game would grow
   its own appearance format.
2. **A character with a `from_base` flag** that skips `render`. Every character Stage would need an "is this a dressed base?"
   branch, and its export (an atlas) would be empty.
3. **One Asset holding a crowd** (a `variants` list). One ID for a dozen figures, so the Manifest can't freeze each, and the
   Owner can't reject or re-roll one without touching the others.
4. **A new Kind, `npc`**, one Asset per figure, whose Stages read the base's and the Wearables' built outputs as inputs that
   cross Assets, as ADR 0012 does for a base.

We chose 4.

## The rule

- **`npc` is a Kind.** `kiripix new npc <name> --base <character>`; `base` is an Asset parameter, as in ADR 0012. The base is a
  character with no base of its own; a Wearable, a sprite or a missing Asset is `npc.base_unknown`.
- **Recipe: choose → export.** Nothing renders. `choose` writes `npc.json`; its input hash covers the base's and each chosen
  Wearable's `sheet` and `palette` outputs, so a re-render of the base or a Wearable makes every NPC on it stale.
- **The choice is parameters of `choose`, not Decisions:** `wearables` (IDs in stack order; default each Wearable's own
  `order`) and `colours` (`part=choice` pairs). A choice is a few names, with nothing drawn on a grid, so it is set like any
  parameter (`kiripix set`), hashed like one, and written by the bulk maker the same way a person sets it. A parameter left at
  its default stays out of the hash.
- **What an NPC may change: Wearables and colours only.** Never the body's clips, `height`, camera or cell. A different height
  or clip set is a character made from the base (ADR 0012), which renders. A background NPC plays the base's exploration clips.
- **Colours are named choices in the ramp table.** `[[character.ramps]]` gains `choices`, a table of named ramps as long as the
  Part's row (`choices = { auburn = [...] }`); an NPC names `hair = "auburn"`. The game's appearance data and Kiripix share
  that one list. A `kiripix.toml` `schema_version` bump with its migration.
- **Export writes one appearance file per NPC** (`npc/<name>/npc.json`: base, Wearables in stack order with their exported
  paths, colours by Part with their ramps), in the Manifest under a frozen ID. No images: the game draws the base's and the
  Wearables' exports. It's refused until the base and each Wearable are exported.
- **Bulk from a seed** (`new npc <prefix> --base … --count N --seed S`) makes N ordinary `npc` Assets. What it may pick from is
  given by the command's flags (`--wearables`, `--choices`), with "every Wearable on the base and every choice" as the
  default; nothing new is stored on the base. The same seed in the same Project gives the same NPCs.
- **Speaking cast stay characters of their own**, with their own faces at 52 px and their portraits.

## Consequences

- The game reads one small file per figure and draws it with the `CharacterSprite` it already has; its atlas cost for a crowd
  is nothing new.
- A change to a base's look carries to every NPC on it through the Stage graph, as a base's clips carry to its characters.
- An NPC can't have a pose, clip or height of its own. When one needs it, it becomes a character made from the base.
- The work tickets are 0356 (the Kind, `choose`, ramp `choices`), 0357 (Checks), 0358 (export), 0359 (bulk) and 0360 (UI).
