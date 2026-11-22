---
status: todo
milestone: later
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0356-m6-npc-kind-and-choose-stage.md]
---

# Later: an NPC's `choose` hashes only the ramp rows it uses

Spec §5 (input hash) and §6.3. Found in [0356](0356-m6-npc-kind-and-choose-stage.md): `choose` declares the whole
`character.ramps` setting as an input, so any edit of the ramp table (a new row, a choice added to another Part) makes every NPC's
`choose` and `export` stale.

## Why it waits

A Stage's settings are hashed per key, so hashing only the rows of the base's Parts needs a new kind of input in the graph (a
setting narrowed by a function of the run). `choose` is cheap (no render, no Runner), and the export after it writes one small JSON
file, so a stale crowd costs one `run --all` of seconds. Worth doing if the Owner finds the stale marks noisy on the status board
once Chapter 1's NPCs exist.

## What to do, when it's taken

- An input that hashes the rows of `character.ramps` whose `name` is a Part of the base (and their `choices`), not the whole key.
- CLI seam: adding a ramp row for a Part the base doesn't have leaves `choose` done; changing a choice the NPC uses makes it stale.
