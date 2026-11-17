---
status: todo
milestone: M5
agent: character-pipeline
type: trial
parent: 0236-m5-the-games-next-needs.md
---

# M5: trial: a thing held in the hand, (a) attached or (c) a layer, and the cell

Spec §6.3 (clips, render) and §16 (open decision 9). Part of [0236](0236-m5-the-games-next-needs.md), item 1. Prototype code
stays in `backlog/m5/0238-trial/`, not in `kiripix/`.

**Moved here from the layer trial** ([0153](0153-m5-character-layer-trial.md), its steps 6–8) by the Owner on 2026-11-16,
because the game needs it two to four game milestones before layers.

## What the game needs

- **M03 (now):** the phone in the MC's `phone` idle (the game's DEC-068).
- **M05:** Sanjay's leaf rake, and the Beast Master's attack with its prop.
- **M06:** the Jazz Musician's battle clips with the instrument in the frames, on both bodies and both outfits (M06-13).

The baseline is [0170](../m4/0170-m4-weapon-in-a-battle-clip-trial.md) (`backlog/m4/0170-trial/`): option (a), a 1 m stick
parented to the right hand in `attack`. Two things stopped it:

- the stick floated beside the fist, because its offset and rotation were guesses;
- the cell grew from 78 to 92 for every clip, idle included (+39 % atlas).

## What to do

On `mc03_male_clothes01`, with two things: the phone (in its `phone` clip, or `idle` until that exists) and the 0170 stick or a
rake (in `attack`).

1. **The grip.** Find how a held thing sits in the hand in every frame. Try an empty (a socket) parented to the hand bone in
   the Model, with the thing parented to it. Or a grip bone, or an offset and rotation per clip. For the generator-built
   Models, say whether `chargen` can add the socket. Show the phone and the stick in all 8 directions at 4x and as a GIF.
2. **(a) attached against (c) a layer.** (a): the thing is in the character's render for that clip only. (c): it's rendered
   alone with the body as a holdout, in the body's cell and pivot, and stacked in the game. Compare them on:
   - the cell and atlas size;
   - render cost;
   - the outline where the thing crosses the body's silhouette;
   - depth by direction (the phone behind the body facing north);
   - the Owner's files in Blender;
   - the Assets needed (both bodies, both outfits, three classes).
3. **The cell.** Measure what (a) costs with the cell as it is (one per character), and with a cell per clip (idle and walk
   keep 78). A cell per clip changes `character.json` (`cell` and `pivot` per clip) and the game's loader. Say what breaks
   and what it saves. Under (c) the body's cell doesn't change, but say how big the layer's cell is.
4. **Colours.** Try the held thing with its own ramp row in the Project ramp table, and with fixed colours outside every
   part. Either way, a skin or hair swap must never touch it. Record which the Owner wants, per thing (the phone is probably
   fixed, an outfit-coloured weapon a row).
5. **Points.** If [0237](0237-m5-render-records-named-points.md) has landed, check that its `hand_r` point and the grip
   agree to a pixel, so the game's fallback and the real thing line up.

## What to record, in this ticket

- The sheets and GIFs, with their paths, and the Owner's view of each.
- The measures for 2 and 3, against 0170's.
- **The Owner's choice of (a) or (c)**, the grip method and the cell rule. Then file the build tickets, each with its agent:
  - for (a): the `attach` field on a `clip` Decision, the import, the parenting, attachment materials numbered after the
    Model's (0170), the cell rule and `describe`;
  - for (c): the weapon part of [0152](0152-m5-character-layers.md) goes first.

## Acceptance criteria

- [ ] The phone and the stick sit in the hand in every frame and direction, on the sheet.
- [ ] (a) and (c) compared on the points above, with numbers.
- [ ] The Owner's choice recorded, the build tickets filed, and spec §6.3 and §16 decision 9 updated to say which.
