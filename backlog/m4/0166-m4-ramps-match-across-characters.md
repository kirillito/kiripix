---
status: todo
milestone: M4
type: spec
depends_on: [0150-m4-palette-ramps-per-part.md, 0151-m4-export-part-ramps.md]
---

# M4: ramps that match across characters

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §6.3 (palette), §9 (Character) and §16 (open decision 9);
[0147](0147-m4-character-palette-ramps.md) (a ramp per part, for one character); [ADR 0009](../../docs/adr/0009-a-rooms-looks-are-a-stage-on-the-room.md)
("the stage graph has no inputs that cross Assets"). The game's needs are in `../urban-mystery-club/docs/MILESTONE_PLANS.md`
(M03) and `docs/DECISION_LOG.md` (DEC-052, DEC-053). Added 2026-11-12. High priority: it comes right after 0150 and 0151.

## Problem Statement

The game's M03 has **four character Assets**: 2 bodies (one per gender) x 2 outfits, each a whole-body variant (DEC-052).
One palette-swap shader recolours skin, hair and clothing on all four, driven by an appearance record (gender, colours,
outfit, class). M03's acceptance: every combination renders correctly, and a skin or hair swap changes no other pixel.

0147 gives each character its own ramps: its own `parts`, its own lengths, its own colours fitted to its own frames, and
`ramps.png`'s rows in that character's order. On four Assets that means four shaders' worth of data:

- the skin may be row 0 on one character and row 2 on another, and 3 steps on one and 4 on another;
- one skin choice ("dark skin") must be stored as four source ramps, one per character, because each character's skin was
  fitted to its own colours.

The game wants one table: the same part names, ramp lengths and `ramps.png` rows on every character, and for skin and hair
ideally the same palette colours, so that one skin choice is one ramp everywhere.

## Solution (decided by the Owner on 2026-11-12: Q1 and Q2 below)

**A Project ramp table**, in `kiripix.toml`:

```toml
[[character.ramps]]              # row 0 of every character's ramps.png
name = "skin"
length = 3
rgb = [[0.42, 0.25, 0.18], [0.66, 0.44, 0.33], [0.85, 0.64, 0.52]]   # shared colours, dark to light (optional)

[[character.ramps]]              # row 1
name = "hair"
length = 3
rgb = [...]

[[character.ramps]]              # row 2: structure only; each character fits its own colours
name = "top"
length = 3
```

- **The table's order is the row order** in every character's `ramps.png` and in `character.json`'s `parts`. Every part in the
  table gets its row on every character; a part a character doesn't have is a transparent row. So a row means the same part
  everywhere, and `metadata/kiripix_parts` is the same list on all four.
- **A part with `rgb` has shared colours:** the `palette` Stage doesn't fit that part's colours, it maps the part's pixels onto
  the given ramp. Every character then has the same palette indexes for it, and the game's swap shader looks for the same
  colours on every body.
- **A part without `rgb` shares only its structure:** name, length and row. Each character fits its own colours, as 0150 does.
  Outfit pieces that differ between outfits fit here.
- **A character's `parts` maps the table's parts to its own materials** (`skin,hair,top=jacket+hood`), since two Models may name
  their materials differently. With an empty table, `parts` works as 0150 built it, so mc02's M4 gate isn't held up.
- **Filling the table:** a Command copies a built character's ramps into it (`kiripix ramps-add character.mc02 --parts
  skin,hair --colours`). That is the proposal's `ramps_from = character.mc02`, done once and explicitly, after which every
  character, mc02 included, reads the table.
- **A Project check** (`check --all`), `palette.parts_differ`: a part has the same length, row and (when shared) colours on
  every character whose `palette` is built, and every exported `character.json` agrees.

### Why a table, not `ramps_from`

The request proposed a `palette` parameter `ramps_from = character.mc02`: reuse that character's part list, lengths and colours.
It would work, but it makes one Asset's Stage read another Asset's output. The stage graph has no such inputs (ADR 0009 turned
down the same thing for Looks), so it would need an ADR, a lock across two Assets, and staleness that crosses them: a rebuild of
mc02's `palette` would make the other three stale, and mc02's rows would follow its own order. [0165](../m5/0165-m5-characters-share-a-base.md)
needs cross-Asset inputs in M5 anyway, so `ramps_from` could ride on them then. The table needs nothing new: `kiripix.toml` is
already an input of every Stage that reads it (the palette, the camera presets), and a table change makes every character's
`palette` stale through the ordinary graph.

## Tickets

| Ticket | What | Agent |
|---|---|---|
| [0167](0167-m4-project-ramp-table.md) | The table in `kiripix.toml` (with a migration), `ramps-add`, the Project check | core-engineer |
| [0168](0168-m4-palette-reads-the-ramp-table.md) | The character `palette` Stage reads the table: lengths, rows, shared colours | character-pipeline |
| [0169](0169-m4-export-ramps-in-project-order.md) | `ramps.png` and `character.json` in the table's order, with empty rows | godot-export |

## Order

| Wave | Tickets |
|---|---|
| 0 | 0150 and 0151 done (mc02 on its own ramps, the M4 gate's swap test) |
| 1 | 0167 |
| 2 | 0168 |
| 3 | 0169 |

Then the four characters: fill the table from the first body (`ramps-add`), set `parts` on each, rebuild from `palette`, export,
and in Godot swap the skin row on all four with the same ramp (the M4 gate, [0142](0142-m4-gate.md)).

**Don't run 0168 alongside 0150:** both edit `kiripix/recipes/character_palette.py`. Don't run 0169 alongside 0151.

## User Stories

1. As the game, I want a part to be the same row with the same length on every character, so that one shader and one
   appearance record serve all four bodies.
2. As the game, I want skin and hair to have the same source colours on every character, so that one skin choice is one ramp
   everywhere.
3. As the Owner, I want outfit pieces to keep colours of their own if they need them, so that a second outfit isn't forced into
   the first's ramps.
4. As the Owner, I want `check --all` to tell me when two characters disagree about a part, so that a swap isn't broken in the
   game first.

## Questions for the Owner

| # | Question | Answer |
|---|---|---|
| Q1 | A Project ramp table (above), or `ramps_from` on the `palette` Stage (needs cross-Asset inputs and an ADR)? | **Answered 2026-11-12: the table.** |
| Q2 | Are ramp **colours** shared, or only the **structure** (names, lengths, rows)? | **Answered 2026-11-12: colours shared for skin and hair** (`rgb` in the table). Every other part, clothing included, shares only its structure. |

## Out of scope

- The game's swap shader and appearance record.
- Characters sharing a rig and clips: M5 ([0165](../m5/0165-m5-characters-share-a-base.md)), and the M4 stop-gap
  [0171](0171-m4-copy-clips-from-a-character.md).
- Ramps for NPCs the game doesn't recolour: they keep `parts` empty, or their own.
