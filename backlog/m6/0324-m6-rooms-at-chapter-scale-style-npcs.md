---
status: todo
milestone: M6
type: spec
---

# M6: rooms at chapter scale, style that holds, NPCs from bases

Background: [the spec](../../docs/KIRIPIX_SPEC.md) §2 (principle 3), §6.1, §6.3, §11 (status board) and §14 (M6, as
re-planned by the Owner on 2026-11-18). The game's plan is `../urban-mystery-club/docs/ROADMAP.md` (M15–M17). Split into
tickets on 2026-11-19, before the M5 gate closes.

## Problem Statement

The game's top risk is room throughput. Its M15–M16 need about 30 Chapter 1 rooms at final art, and Kiripix makes about one
room per game milestone today. M5's first-pass skill cut the Owner's time on one room to 2.95 minutes in the UI
([0249](../m5/0249-m5-room-first-pass-workflow.md)), but each room is still started by hand, one session at a time, and
the Owner finds each room's stops by opening it. Thirty rooms means thirty sessions and thirty walks through the status
board.

The game's high risk is a mixed look: 3D characters, painted rooms and imported sprites drift apart, and nothing measures
it. Principle 3 says consistency is "enforced by checks, not by memory", but no Check compares one Asset's style with another's.

The game's M17 needs Chapter 1's NPCs. Kiripix can render a base body and Wearables over it (M5), and the game has a swap
shader, but nothing makes a background NPC from those parts without a new render.

## Solution

**Rooms at chapter scale.** A chapter's rooms go through their first passes without the Owner, and the Owner then reviews
every room's stops in one sitting:
- **First passes over a list of rooms** ([0331](0331-m6-first-passes-over-a-list-of-rooms.md)): the
  `room-first-pass` skill runs one fresh session per room, in sequence, and each room stops where it needs the Owner. Each
  stop leaves a **hand-over note** on its Stage ([0326](0326-m6-hand-over-note.md)).
- **A review queue** ([0325](0325-m6-review-queue-command.md), [0329](0329-m6-ui-review-queue.md)): every Stage in
  `needs-review`, every `needs-input` that only the Owner can answer and every finding with an `owner_action`, across all
  Assets, in one keyboard flow.
- **The batch view for whole districts**, moved here from Later ([0327](0327-m6-match-scope.md),
  [0328](0328-m6-district-probe.md), [0330](0330-m6-ui-district-view.md)): a district's rooms side by side, with their status,
  their Exits and what's waiting, and `run`, `check` and `export` over the district.

**A style match Check across Kinds.** The Owner picks reference Assets. A Check scores an Asset against them on palette
use, the range of value and saturation, outline density, pixel scale and light direction, using deterministic Ops. A trial
on the Project's real Assets ([0332](0332-m6-style-match-trial.md)) picks the measures that tell matched from mismatched,
and their thresholds. Values marked "set by 0332" in the work tickets ([0333](0333-m6-style-measures-and-check.md),
[0334](0334-m6-style-references-and-wiring.md), [0335](0335-m6-ui-style-scores.md)) come from it.

**NPC variants from a base.** A background NPC is a base body, some Wearables and a colour per Part, with no new render. The
design has open questions, chiefly whether Kiripix or the game holds an NPC's appearance, so it has its own spec ticket
([0336](0336-m6-npc-variants-from-a-base.md)) that the Owner answers before its work tickets are written. A preview that
stacks Wearables and swaps ramps on the cast sheet ([0337](0337-m6-cast-sheet-stacks-and-swaps.md)) is needed whichever way
it's answered, so it goes first.

### Added on 2026-11-19, for the game's M06–M10 (the Owner's choice)

M6 runs while the game works through its M04 to about M10. These four help it sooner than chapter scale does:

- **Room Sources in bulk.** With first passes automated, making each Source becomes the Owner's biggest cost per room. The brief
  renders the room's prompt from the Project's template and style bible, without a Provider
  ([0348](0348-m6-brief-renders-the-prompt.md)). `to-paint` writes every prompt and canvas a district needs into one folder
  ([0349](0349-m6-to-paint-pack.md)). `inbox` imports what comes back by file name ([0350](0350-m6-source-inbox.md)). The
  district view shows the rooms that wait for a Source ([0351](0351-m6-ui-rooms-waiting-for-a-source.md)).
- **Normal maps for painted rooms** (game M10, its ISS-020). The Owner approved them on 2026-11-18 after
  [0252](../m5/0252-m5-environment-normals-trial.md), and its four outlined tickets are filed here: an ADR for the Stage
  ([0339](0339-m6-adr-room-normals-stage.md)), the depth Runner ([0340](0340-m6-depth-runner.md)), the `normals` Stage
  ([0341](0341-m6-room-normals-stage.md)), the export ([0342](0342-m6-export-room-normals.md)) and the UI
  ([0343](0343-m6-ui-room-normals.md)). Per ADR 0004 the Stage goes before `palette`, not after it as 0252 outlined. It is
  off by default, so no existing room rebuilds.
- **Named terrain Masks** (game M09, a grid battle in a large room), moved from Later. A Project can already name extra
  Masks, so what's missing is a Command to add one ([0344](0344-m6-mask-add.md)), their export with frozen names
  ([0345](0345-m6-export-named-masks.md)) and the masks screen ([0346](0346-m6-ui-named-masks.md)).
- **Battle effects** (game M06 placeholders, M18), moved from Later as a trial first ([0347](0347-m6-vfx-trial.md)). It
  tests whether an effect is a `sprite` with a few parameters before designing a Kind, and files the build tickets.

## Questions for the Owner

Each has a recommendation. The tickets are written to the recommendation, so a different answer changes the ticket named.

| # | Question | Recommendation | Ticket |
|---|---|---|---|
| Q1 | What is a **district**? | The rooms whose IDs share a prefix, given as a glob (`room.ch01_dungeon_*`). No new field and no new data: the ch01 rooms are already named this way. "District" goes in the glossary as a word for that set. | 0327, 0328 |
| Q2 | Does a session leave a **hand-over note** on the Stage where it stops, or only report at the end? | A note on the Stage (`kiripix note`), shown in the review queue beside the stop. A report in a transcript is lost by the time the Owner reviews 30 rooms. | 0326 |
| Q3 | Does the queue hold **findings an agent could fix** (a `fix` command)? | No. They're counted, with their commands, so a session clears them before the Owner sits down. The queue holds only what the Owner owns. | 0325 |
| Q4 | Who picks the **style references**? | The Owner only: `style-add` is owner-only, so a session can't make a mismatch pass by changing what it's measured against. | 0334 |
| Q5 | How strict is the **style Check** in M6? | Warnings only, never blocking `export`, until the gate shows it rarely misfires. Then the Owner may raise chosen codes to errors. | 0333 |
| Q6 | **0143 and 0144** sit in `backlog/m6/` with `milestone: M6`, but the spec moved them out of M6. | Set their `milestone` to `later` and leave the files where they are, so their links still work. | 0143, 0144 |

The NPC questions are in [0336](0336-m6-npc-variants-from-a-base.md).

## Order

| Wave | Area | Tickets |
|---|---|---|
| 1 | Foundations, and what the game needs first | [0327](0327-m6-match-scope.md) the `--match` scope, [0326](0326-m6-hand-over-note.md) the hand-over note, [0332](0332-m6-style-match-trial.md) the style trial, [0337](0337-m6-cast-sheet-stacks-and-swaps.md) the stacked cast sheet; [0347](0347-m6-vfx-trial.md) the VFX trial (game M06); [0344](0344-m6-mask-add.md) named Masks; [0339](0339-m6-adr-room-normals-stage.md) the normals ADR; [0348](0348-m6-brief-renders-the-prompt.md) the prompt |
| 2 | The queue, the district, Sources | [0325](0325-m6-review-queue-command.md), then [0329](0329-m6-ui-review-queue.md); [0328](0328-m6-district-probe.md), then [0330](0330-m6-ui-district-view.md); [0349](0349-m6-to-paint-pack.md), then [0350](0350-m6-source-inbox.md), then [0351](0351-m6-ui-rooms-waiting-for-a-source.md); [0345](0345-m6-export-named-masks.md) and [0346](0346-m6-ui-named-masks.md) (game M09) |
| 3 | Rooms without the Owner; room normals | [0331](0331-m6-first-passes-over-a-list-of-rooms.md): the skill's batch mode, then the run on the ch01 rooms that have Sources; [0340](0340-m6-depth-runner.md), [0341](0341-m6-room-normals-stage.md), [0342](0342-m6-export-room-normals.md), [0343](0343-m6-ui-room-normals.md) (game M10) |
| 4 | Style; effects | [0333](0333-m6-style-measures-and-check.md), then [0334](0334-m6-style-references-and-wiring.md), then [0335](0335-m6-ui-style-scores.md); the build tickets [0347](0347-m6-vfx-trial.md) files |
| 5 | NPCs | The work tickets [0336](0336-m6-npc-variants-from-a-base.md) files, after the Owner's answers |
| Gate | | [0338](0338-m6-gate.md) |

A wave is a priority, not a barrier: a ticket with no open dependency may start early. The NPCs come last because the game
needs them at its M17, after the rooms at its M15–M16; the stacked cast sheet goes first because it's small and the Owner
needs it to answer 0336. The game's own order puts effects (M06), named Masks (M09) and room normals (M10) ahead of chapter
scale (M15), so when agents are short, those go first.

**Don't run these at the same time, because they edit the same files:**
- 0325, 0326 and 0327 (`kiripix/commands/project.py`, the status code in `kiripix/core/`). 0327 first.
- 0329, 0330, 0335, 0343, 0346 and 0351 (`web/src/App.tsx`, `components.tsx`).
- 0334, 0350 and any ticket that bumps `kiripix.toml`'s `schema_version`. They take turns, each with its migration.
- 0342 and 0345: both bump `room.json`'s `schema_version`.
- 0341, 0344 and 0348 (`kiripix/recipes/room.py`).

## What can run without the Owner

Every wave 1, 2 and 4 ticket is coded and tested by its agent alone, with at most an eye check at the end. The Owner is
needed for: the trial's verdict on which mismatches matter (0332), picking the style references (0334, owner-only by Q4), the
answers in 0336, painting the rooms' Sources before 0331's run, and the review sitting at the gate. The new tickets add: the
VFX trial's verdict (0347), accepting the normals ADR (0339), the first prompt template with the Owner (0348), and eye checks
on the normals (0341, 0343).

## User Stories

1. As the Owner, I want a list of rooms to go through their first passes while I'm away, so that I come back to rooms that
   only need my decisions.
2. As the Owner, I want every stop across every room in one queue that I step through with the keyboard, so that I approve a
   district's first passes in one sitting without opening each room.
3. As the Owner, I want the session's note on why it stopped, beside the stop, so that I don't reconstruct its reasoning.
4. As the Owner, I want to see a district's rooms side by side with their Exits and what each is waiting on, so that I see
   which rooms are done and which Exits don't pair.
5. As an agent, I want `run`, `check`, `export` and `status` over a district, so that I work on a chapter's rooms without
   listing their IDs.
6. As the Owner, I want a warning when a sprite, a room or a character drifts from the references I picked, with the numbers,
   so that a mismatch is caught before it reaches the game, not at a playtest.
7. As the Owner, I want to see a body with its Wearables stacked and its colours swapped, beside other figures, so that I can
   judge an NPC before anything is exported.
8. As the game, I want many background NPCs from one base, with no new render, so that Chapter 1's cast costs data, not
   render minutes.
9. As the Owner, I want every prompt and canvas a district needs in one folder, and the images I save to land in the right
   rooms by their names, so that making Sources is painting, not filing.
10. As the game, I want a dark tunnel's walls to catch the flashlight, from a normal map Kiripix makes for the room.
11. As the game, I want `cover` and `water` painted on a room and exported as exact images, so that my battle grid reads
    terrain per cell.
12. As the game, I want battle effects (a hit spark, a sound wave, a summon's puff) as sheets that sit beside the cast.

## Out of scope

- Generation and agents (the MCP adapter, PixelLab, an image API Provider and `gen`, image-to-3D, local generation): deferred
  with no milestone (spec §14).
- The tileset recipe: Later, after the trial chose painted rooms for chapter 1 ([0251](../m5/0251-m5-tileset-trial.md)).
- Still under Later: side view, "promote to Prop" for a room's foreground Layer, and renaming exported IDs with aliases.
- Normals for a Look that changes a room's geometry (ADR 0339 records it as open). Particles and screen shake: the game's.
- Kiripix starting Claude sessions itself. The batch of first passes is driven from the art Project by the skill; Kiripix
  stays a tool the session calls (§1).
- A district's room layout on a map. The district view lists the rooms and their Exits; placing rooms by their Exits' sides
  is a later step if the Owner wants it.
- The game's compositor and its appearance data (as in [0152](../m5/0152-m5-character-layers.md)), unless 0336's Q1 moves an
  NPC's appearance into Kiripix.
